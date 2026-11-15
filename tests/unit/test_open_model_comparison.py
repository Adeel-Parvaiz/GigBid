import json
from types import SimpleNamespace

import httpx

from agent.config import load_config
from agent.handoffs import JobSpec
from evals.runners.open_model_comparison import MeasuredLLM, summarize


async def test_writer_preserves_trusted_job_and_screening_questions():
    from agent.handoffs import Claim, ProposalDraft
    from agent.nodes.writer import make

    class WrongMetadataLLM:
        async def structured(self, *args):
            return ProposalDraft(job_id="another-job", questions=["Invented question?"],
                                 claims=[Claim(text="I have 12 years of experience.", kind="logistics")])

    node = make(SimpleNamespace(llm=WrongMetadataLLM(), memory=None))
    state = {"job": {}, "job_spec": {"job_id": "correct-job", "title": "Build", "screening_questions": []},
             "fit_report": {"score": 0.0}, "evidence": [], "profile": {}}
    result = await node(state)
    assert result["proposal_draft"].job_id == "correct-job"
    assert result["proposal_draft"].questions == []
    assert result["proposal_draft"].claims == []


async def test_measurement_counts_schema_repair_tokens_and_preserves_model():
    responses = ['{"job_id":"j"}', '{"job_id":"j","title":"Build"}']
    calls = []

    async def record(response):
        await llm.record(response)

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": responses[len(calls) - 1]}}],
                                       "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), event_hooks={"response": [record]}) as client:
        llm = MeasuredLLM(load_config(), client)
        answer = await llm.structured("analyst", JobSpec, {"job": {"title": "Build"}})
    assert answer.title == "Build"
    assert len(llm.calls) == 2
    assert all(c["node"] == "analyst" and c["prompt_tokens"] == 10 for c in llm.calls)
    assert all(c["model"] == "qwen3:4b-instruct" for c in llm.calls)


def test_failed_jobs_count_against_accuracy_and_missing_usage_is_not_zero():
    rows = [{"completed": True, "action": "bid", "gold": "bid", "seconds": 1,
             "scam_pred": False, "scam_gold": False, "claims_total": 0,
             "calls": [{"prompt_tokens": None, "completion_tokens": None}]},
            {"completed": False, "gold": "skip", "seconds": 3, "calls": []}]
    result = summarize(rows)
    assert result["accuracy_including_errors"] == 0.5
    assert result["errors"] == 1
    assert result["usage_complete"] is False and result["prompt_tokens"] is None
    assert result["latency_seconds_p95"] == 3
