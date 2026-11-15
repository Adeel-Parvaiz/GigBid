"""LLM access. Model per node comes from config (never code). Two backends:

* HeuristicLLM: deterministic offline test double so graph logic, approvals and persistence are testable.
* OpenAICompatLLM: any OpenAI-compatible server (Ollama, vLLM, Groq, OpenRouter, Together).

Untrusted job text is only ever passed inside <data> tags, never concatenated into instructions.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent.handoffs import Claim, Critique, IntentResult, JobSpec, ParagraphRewrite, ProposalDraft, ReplyDraft, RiskReport
from agent.token_budget import current_token_budget, estimate_tokens

T = TypeVar("T", bound=BaseModel)
PROMPTS = Path(__file__).with_name("prompts")


class LLM(Protocol):
    async def structured(self, node: str, schema: type[T], inputs: dict[str, Any]) -> T: ...


def load_prompt(node: str) -> str:
    return (PROMPTS / f"{node}.md").read_text()


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class OpenAICompatLLM:
    def __init__(self, cfg: dict, client: httpx.AsyncClient | None = None):
        prof = cfg["llm"]["profiles"][cfg["llm"]["profile"]]
        self.base_url, self.models = prof["base_url"].rstrip("/"), prof["nodes"]
        self.fallback_models = prof.get("fallback_nodes", {})
        self.max_output_tokens = prof.get("max_output_tokens")
        key = os.environ.get(prof.get("api_key_env", ""), "")
        self.headers = {"Authorization": f"Bearer {key}"} if key else {}
        self.client = client or httpx.AsyncClient(timeout=120)

    async def structured(self, node: str, schema: type[T], inputs: dict[str, Any]) -> T:
        messages = [
            {"role": "system", "content": load_prompt(node) + "\n" + json.dumps(schema.model_json_schema())},
            {"role": "user", "content": f"<data>{json.dumps(_jsonable(inputs), default=str)}</data>"},
        ]
        primary = self.models.get(node, self.models.get("writer"))
        models = [primary]
        fallback = self.fallback_models.get(node, self.fallback_models.get("writer"))
        if fallback and fallback != primary:
            models.append(fallback)
        last_err = ""
        for model in models:
            model_messages = list(messages)
            for _ in range(2):  # one repair attempt per model
                body = {"model": model, "messages": model_messages, "temperature": 0,
                        "response_format": {"type": "json_schema",
                                            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}}
                budget = current_token_budget.get()
                prompt = json.dumps(model_messages, ensure_ascii=False)
                if budget is not None:
                    available_output = budget.output_limit(prompt)
                    body["max_tokens"] = min(self.max_output_tokens or available_output, available_output)
                elif self.max_output_tokens is not None:
                    body["max_tokens"] = self.max_output_tokens
                try:
                    started = time.perf_counter()
                    response_obj = await self.client.post(
                        f"{self.base_url}/chat/completions", json=body, headers=self.headers
                    )
                    response_obj.raise_for_status()
                    response = response_obj.json()
                    elapsed = time.perf_counter() - started
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in {408, 429, 500, 502, 503, 504} or model == models[-1]:
                        raise
                    break
                except httpx.TransportError:
                    if model == models[-1]:
                        raise
                    break
                text = response["choices"][0]["message"]["content"]
                if budget is not None:
                    usage = response.get("usage") or {}
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    exact_usage = prompt_tokens is not None and completion_tokens is not None
                    if not exact_usage:
                        prompt_tokens = estimate_tokens(prompt)
                        completion_tokens = estimate_tokens(text)
                    token_count = usage.get("total_tokens")
                    if token_count is None:
                        token_count = prompt_tokens + completion_tokens
                    budget.record(token_count)
                    budget.record_call(model, prompt_tokens, completion_tokens, elapsed, exact_usage, token_count)
                try:
                    return schema.model_validate_json(text)
                except ValidationError as error:
                    last_err = str(error)
                    model_messages += [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": f"Invalid JSON for schema: {last_err[:500]}. Return corrected JSON only."},
                    ]
        raise ValueError(f"{node}: model did not return valid {schema.__name__}: {last_err[:200]}")


class HeuristicLLM:
    """Test double. Deterministic, truthful-by-construction writer; the safety logic under test lives elsewhere."""

    async def structured(self, node: str, schema: type[T], inputs: dict[str, Any]) -> T:
        started = time.perf_counter()
        budget = current_token_budget.get()
        prepared = _jsonable(inputs)
        prompt = ""
        if budget is not None:
            prompt = load_prompt(node) + json.dumps(schema.model_json_schema()) + json.dumps(prepared, default=str)
            budget.output_limit(prompt)
        result = getattr(self, f"_{node}")(prepared)
        if budget is not None:
            output = json.dumps(_jsonable(result), default=str)
            input_tokens, output_tokens = estimate_tokens(prompt), estimate_tokens(output)
            budget.record(input_tokens + output_tokens)
            budget.record_call("heuristic", input_tokens, output_tokens, time.perf_counter() - started, False,
                               input_tokens + output_tokens)
        return result  # type: ignore[no-any-return]

    def _analyst(self, i: dict) -> JobSpec:
        job = i["job"]
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", job["description"]) if s.strip()]
        b = job.get("budget") or {}
        return JobSpec(job_id=job["job_id"], title=job["title"], deliverables=sentences[:3],
                       required_skills=job.get("required_skills", []), budget_min=b.get("min"),
                       budget_max=b.get("max"), duration_days=job.get("duration_days"),
                       screening_questions=job.get("screening_questions", []))

    def _risk(self, i: dict) -> RiskReport:
        return RiskReport(score=0.0, flags=[], explanation="heuristic double: no extra signals")

    def _writer(self, i: dict) -> ProposalDraft:
        spec, evidence = i["job_spec"], i["evidence"]
        wanted = set(i.get("fit_report", {}).get("evidence_ids", []))
        evs = [e for e in evidence if e["evidence_id"] in wanted] or evidence
        rules = " ".join(i.get("style_rules") or [])
        claims = [] if "Do not open with" in rules else [
            Claim(text=f"Your post for \"{spec['title']}\" is close to work I have done before.", kind="boilerplate")]
        for e in evs[:3]:
            claims.append(Claim(text=f"{e['title']}: {e['summary']}", evidence_ids=[e["evidence_id"]]))
        claims.append(Claim(text="I would be glad to talk through scope and timeline here on the platform.", kind="boilerplate"))
        for n, _q in enumerate(spec.get("screening_questions", [])):
            if evs:
                claims.append(Claim(text=evs[0]["summary"], evidence_ids=[evs[0]["evidence_id"]], section=f"screening:{n}"))
        return ProposalDraft(job_id=spec["job_id"], questions=spec.get("screening_questions", []), claims=claims)

    def _paragraph_rewriter(self, i: dict) -> ParagraphRewrite:
        evidence = i["evidence"][0]
        return ParagraphRewrite(
            text=evidence["summary"],
            evidence_ids=[evidence["evidence_id"]],
        )

    def _liaison_intent(self, i: dict) -> IntentResult:
        t = i["message"].lower()
        if re.search(r"\b(call|meeting|meet|interview|schedule)\b", t):
            return IntentResult(intent="interview_request", rationale="asks to meet")
        if re.search(r"\b(price|budget|rate|discount|cheaper)\b", t):
            return IntentResult(intent="negotiation", rationale="talks price")
        return IntentResult(intent="question", rationale="default")

    def _liaison_reply(self, i: dict) -> ReplyDraft:
        tid, intent, ev = i["thread_id"], i["intent"], i.get("evidence", [])
        claims = [Claim(text="Thanks for getting back to me.", kind="boilerplate")]
        if intent == "question":
            if ev:
                claims.append(Claim(text=ev[0]["summary"], evidence_ids=[ev[0]["evidence_id"]]))
            else:
                claims.append(Claim(text="Let me check the details and come back to you here.", kind="boilerplate"))
        elif intent == "negotiation":
            claims.append(Claim(text="Happy to talk about scope and price here on the platform.", kind="boilerplate"))
        return ReplyDraft(thread_id=tid, claims=claims)

    def _critic(self, i: dict) -> Critique:
        c, draft = i["criteria"], i["draft"]
        text, issues = draft["cover_letter"], []
        words = len(text.split())
        if words < c["min_words"]:
            issues.append(f"too_short ({words} words)")
        if words > c["max_words"]:
            issues.append(f"too_long ({words} words)")
        if re.search(c["generic_openers"], text.strip()):
            issues.append("generic_opening")
        if not any(cl["evidence_ids"] for cl in draft["claims"] if cl["section"] == "cover"):
            issues.append("no_evidence_backed_claim")
        skills = [s.lower() for s in i["job_spec"].get("required_skills", [])]
        if skills and not any(s in text.lower() for s in skills):
            issues.append("not_personalised_to_requirements")
        return Critique(passed=not issues, score=max(0.0, 1 - 0.25 * len(issues)), issues=issues)


def build_llm(cfg: dict) -> LLM:
    backend = os.environ.get("LLM_BACKEND") or cfg["llm"]["backend"]
    return OpenAICompatLLM(cfg) if backend == "openai_compat" else HeuristicLLM()
