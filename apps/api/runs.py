"""Run manager: drives LangGraph threads in the background, streams their progress, resumes approvals.

* thread_id == run_id, and every run belongs to one user (tenant scoping).
* The run registry is persisted (SQLite) next to the checkpointer, so a pending approval survives an API
  restart: the interrupt payload is read back from the checkpoint, not from memory.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from threading import RLock
from typing import Any

from fastapi.encoders import jsonable_encoder
from langgraph.types import Command

from agent.deps import Deps
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from agent.marketplace_port import MarketplaceError
from agent.tracing import current_trace_id, new_trace_id
from apps.api.storage import serialized


class RunStore:
    COLS = "run_id,user_id,kind,target,status,trace_id,degraded,created_at,outcome,origin"

    def __init__(self, db: str = ":memory:"):
        self._db_lock = RLock()
        self.db = sqlite3.connect(db, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=5000")
        if db != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(f"CREATE TABLE IF NOT EXISTS runs({self.COLS.replace(',', ' TEXT,')} TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS settings(user_id TEXT PRIMARY KEY, json TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS searches(user_id TEXT, query TEXT, PRIMARY KEY(user_id, query))")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS run_events("
            "run_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL, "
            "PRIMARY KEY(run_id, seq))"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS dead_letters("
            "run_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL, "
            "reason TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS extra_llm_usage("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self.db.commit()

    @staticmethod
    def _row(r) -> dict:
        return {"run_id": r[0], "user_id": r[1], "kind": r[2], "target": r[3], "status": r[4], "trace_id": r[5],
                "degraded": r[6] == "1", "created_at": float(r[7]), "outcome": r[8] or None, "origin": r[9]}

    @serialized
    def create(self, user_id, kind, target, origin="api") -> dict:
        run = {"run_id": f"{kind}-{uuid.uuid4().hex[:10]}", "user_id": user_id, "kind": kind, "target": target,
               "status": "running", "trace_id": new_trace_id(), "degraded": False, "created_at": time.time(), "outcome": None,
               "origin": origin}
        self.db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)", (run["run_id"], user_id, kind, target, "running",
                                                                         run["trace_id"], "0", str(run["created_at"]), "", origin))
        self.db.commit()
        return run

    @serialized
    def update(self, run_id, **kw) -> None:
        for k, v in kw.items():
            self.db.execute(f"UPDATE runs SET {k}=? WHERE run_id=?", ("1" if v is True else "0" if v is False else str(v or ""), run_id))
        self.db.commit()

    @serialized
    def get(self, run_id) -> dict | None:
        r = self.db.execute(f"SELECT {self.COLS} FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._row(r) if r else None

    @serialized
    def list(self, user_id) -> list[dict]:
        rows = self.db.execute(f"SELECT {self.COLS} FROM runs WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [self._row(r) for r in rows]

    @serialized
    def all_degraded(self) -> list[dict]:
        return [self._row(r) for r in self.db.execute(f"SELECT {self.COLS} FROM runs WHERE degraded='1'").fetchall()]

    @serialized
    def record_dead_letter(self, run_id: str, reason: str) -> None:
        run = self.get(run_id)
        if run is None:
            raise ValueError(f"unknown run {run_id!r}")
        self.db.execute(
            "INSERT OR REPLACE INTO dead_letters VALUES (?,?,?,?,?,?)",
            (run_id, run["user_id"], run["kind"], run["target"], reason[:1000], time.time()),
        )
        self.db.commit()

    @serialized
    def dead_letter_reason(self, run_id: str) -> str | None:
        row = self.db.execute("SELECT reason FROM dead_letters WHERE run_id=?", (run_id,)).fetchone()
        return row[0] if row else None

    @serialized
    def list_dead_letters(self, user_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT d.run_id,d.kind,d.target,d.reason,d.created_at FROM dead_letters d "
            "JOIN runs r ON r.run_id=d.run_id WHERE d.user_id=? AND r.status='dead_letter' "
            "ORDER BY d.created_at DESC",
            (user_id,),
        ).fetchall()
        return [{"run_id": r[0], "kind": r[1], "target": r[2], "reason": r[3], "created_at": r[4]}
                for r in rows]

    @serialized
    def record_extra_usage(self, run_id: str, usage: list[dict]) -> None:
        self.db.executemany(
            "INSERT INTO extra_llm_usage(run_id,payload) VALUES (?,?)",
            [(run_id, json.dumps(call)) for call in usage],
        )
        self.db.commit()

    @serialized
    def extra_usage(self, run_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT payload FROM extra_llm_usage WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    @serialized
    def append_event(self, run_id: str, event: dict) -> dict:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM run_events WHERE run_id=?", (run_id,)
            ).fetchone()
            stored = {**event, "seq": row[0]}
            self.db.execute(
                "INSERT INTO run_events(run_id, seq, payload) VALUES (?, ?, ?)",
                (run_id, stored["seq"], json.dumps(stored, default=str)),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return stored

    @serialized
    def events_after(self, run_id: str, after: int = 0) -> list[dict]:
        rows = self.db.execute(
            "SELECT payload FROM run_events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    @serialized
    def last_event_seq(self, run_id: str) -> int:
        row = self.db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()
        return int(row[0])

    @serialized
    def claim_status(self, run_id: str, user_id: str, expected: str, new_status: str) -> bool:
        cursor = self.db.execute(
            "UPDATE runs SET status=? WHERE run_id=? AND user_id=? AND status=?",
            (new_status, run_id, user_id, expected),
        )
        self.db.commit()
        return cursor.rowcount == 1

    @serialized
    def clear_dead_letter(self, run_id: str) -> None:
        self.db.execute("DELETE FROM dead_letters WHERE run_id=?", (run_id,))
        self.db.commit()

    @serialized
    def find_active(self, user_id, kind, target) -> dict | None:
        r = self.db.execute(f"SELECT {self.COLS} FROM runs WHERE user_id=? AND kind=? AND target=? AND status NOT IN "
                            "('failed','superseded','needs_attention','queued_degraded','dead_letter','error') ORDER BY created_at DESC",
                            (user_id, kind, target)).fetchone()
        return self._row(r) if r else None

    @serialized
    def get_settings(self, user_id) -> dict:
        r = self.db.execute("SELECT json FROM settings WHERE user_id=?", (user_id,)).fetchone()
        return json.loads(r[0]) if r else {}

    @serialized
    def put_settings(self, user_id, data: dict) -> None:
        self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (user_id, json.dumps(data)))
        self.db.commit()

    @serialized
    def searches(self, user_id=None) -> list[tuple[str, str]]:
        q, a = ("SELECT user_id,query FROM searches WHERE user_id=?", (user_id,)) if user_id else ("SELECT user_id,query FROM searches", ())
        return [tuple(r) for r in self.db.execute(q, a).fetchall()]

    @serialized
    def add_search(self, user_id, query) -> None:
        self.db.execute("INSERT OR IGNORE INTO searches VALUES (?,?)", (user_id, query))
        self.db.commit()

    @serialized
    def remove_search(self, user_id, query) -> None:
        self.db.execute("DELETE FROM searches WHERE user_id=? AND query=?", (user_id, query))
        self.db.commit()

    @serialized
    def mark_orphans(self, origin: str = "api") -> None:
        """A run that was 'running' when ITS process died needs a human to retry it (each process only owns its own)."""
        self.db.execute("UPDATE runs SET status='needs_attention' WHERE status='running' AND origin=?", (origin,))
        self.db.commit()


class RunManager:
    def __init__(self, deps: Deps, checkpointer, store: RunStore | None = None, origin: str = "api"):
        self.deps, self.store, self.origin = deps, store or RunStore(), origin
        self.store.mark_orphans(origin)
        self.graphs = {"bid": build_bid_graph(deps, checkpointer), "conv": build_conversation_graph(deps, checkpointer)}
        self.tasks: set[asyncio.Task] = set()
        self.recovery_lock = asyncio.Lock()

    def cfg(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _emit(self, run_id: str, ev: dict) -> None:
        self.store.append_event(run_id, ev)

    async def start(self, user: dict, kind: str, target: str) -> dict:
        run, created = await self._prepare(user, kind, target, self.origin)
        if created:
            self._spawn(run, self._input(run, user))
        return run

    async def prepare_worker(self, user: dict, kind: str, target: str) -> tuple[dict, bool]:
        """Create a run for ARQ without starting graph work in the API process."""
        return await self._prepare(user, kind, target, "worker")

    async def _prepare(self, user: dict, kind: str, target: str, origin: str) -> tuple[dict, bool]:
        if kind == "bid" and (existing := self.store.find_active(user["user_id"], kind, target)):
            if existing["status"] in {"running", "submitted"}:
                return existing, False
            prior = await self.values(existing)
            if prior.get("profile") == self._profile(user):
                return existing, False
            self.store.update(existing["run_id"], status="superseded")
        run = self.store.create(user["user_id"], kind, target, origin)
        return run, True

    def _input(self, run: dict, user: dict) -> dict:
        profile = self._profile(user)
        if hasattr(self.deps.port, 'binding'):
            profile['_marketplace_binding'] = self.deps.port.binding(user['user_id'])
        return {"job_id": run["target"], "profile": profile} if run["kind"] == "bid" else {"thread_id": run["target"], "profile": profile}

    async def run_blocking(self, user: dict, kind: str, target: str) -> dict:
        """Worker entry point: same run, but awaited. Idempotent: an existing live run for the target is reused."""
        if (existing := self.store.find_active(user["user_id"], kind, target)):
            return existing
        run = self.store.create(user["user_id"], kind, target, self.origin)
        self.store.update(run["run_id"], status="running")
        await self._drive(run, self._input(run, user))
        return self.store.get(run["run_id"])

    async def run_existing(self, run_id: str, user: dict) -> dict:
        run = self.store.get(run_id)
        if run is None or run["user_id"] != user["user_id"]:
            raise ValueError(f"unknown run {run_id!r}")
        if run["status"] not in {"running", "needs_attention"}:
            return run
        graph = self.graphs[run["kind"]]
        snapshot = await graph.aget_state(self.cfg(run_id))
        initial_input = self._input(run, user) if not snapshot.values and not snapshot.next else None
        self.store.update(run_id, status="running")
        await self._drive(run, initial_input)
        return self.store.get(run_id)

    async def resume_blocking(self, run_id: str, user: dict, decision: dict) -> dict:
        run = self.store.get(run_id)
        if run is None or run["user_id"] != user["user_id"]:
            raise ValueError(f"unknown run {run_id!r}")
        if run["status"] != "running":
            return run
        graph = self.graphs[run["kind"]]
        snapshot = await graph.aget_state(self.cfg(run_id))
        interrupted = any(task.interrupts for task in snapshot.tasks)
        await self._drive(run, Command(resume=decision) if interrupted else None)
        return self.store.get(run_id)

    def _profile(self, user: dict) -> dict:
        """Persona + the user's own settings (rates, Connects budget, autonomy) from the Settings screen."""
        from agent.runtime import load_sample_profile
        profile = {**load_sample_profile(user["freelancer_id"]), **self.store.get_settings(user["user_id"])}
        if hasattr(self.deps.port, 'binding'):
            profile['_marketplace_binding'] = self.deps.port.binding(user['user_id'])
        return profile

    def _spawn(self, run: dict, inp: Any, cfg: dict | None = None) -> None:
        self.store.update(run["run_id"], status="running")
        t = asyncio.create_task(self._drive(run, inp, cfg))
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)

    async def _drive(self, run: dict, inp: Any, cfg: dict | None = None) -> None:
        rid, graph = run["run_id"], self.graphs[run["kind"]]
        cfg = cfg or self.cfg(rid)
        tok = current_trace_id.set(run["trace_id"])
        from agent.marketplace_context import marketplace_user
        from mcp_servers.marketplace.adapters.upwork_live import marketplace_binding
        user_token = marketplace_user.set(run['user_id'])
        if isinstance(inp, dict):
            binding = inp.get('profile', {}).get('_marketplace_binding')
        else:
            saved = await graph.aget_state(cfg)
            binding = (saved.values or {}).get('profile', {}).get('_marketplace_binding')
        # Checkpoints created before live integration were simulator runs; never retarget them live.
        binding_token = marketplace_binding.set(binding or 'simulator')
        self._emit(rid, {"type": "started", "trace_id": run["trace_id"]})
        try:
            async for chunk in graph.astream(inp, cfg, stream_mode="updates"):
                for node, upd in chunk.items():
                    if node != "__interrupt__":
                        self._emit(rid, {"type": "node", "node": node, "wrote": sorted(upd) if isinstance(upd, dict) else []})
            status, pend = await self._settle(run)
            self._emit(rid, {"type": "interrupt", "payload": pend} if pend else {"type": "done", "status": status})
        except Exception as e:  # noqa: BLE001
            snapshot = await graph.aget_state(cfg)
            values = snapshot.values or {}
            write_may_have_started = any(values.get(k) for k in ("approval", "submission", "send_result"))
            recoverable_marketplace_error = isinstance(e, MarketplaceError) and e.code in {
                "marketplace_unavailable", "rate_limited"
            }
            degraded = recoverable_marketplace_error and not write_may_have_started
            status = "queued_degraded" if degraded else "needs_attention" if write_may_have_started else "dead_letter"
            if status == "dead_letter":
                self.store.record_dead_letter(rid, f"{type(e).__name__}: {e}")
            self.store.update(rid, status=status, degraded=degraded)
            self._emit(rid, {"type": "error", "message": str(e)[:300]})
            self._emit(rid, {"type": "done", "status": status})
        finally:
            current_trace_id.reset(tok)
            marketplace_user.reset(user_token)
            marketplace_binding.reset(binding_token)

    async def _settle(self, run: dict) -> tuple[str, dict | None]:
        snap = await self.graphs[run["kind"]].aget_state(self.cfg(run["run_id"]))
        pend = next((i.value for t in snap.tasks for i in t.interrupts), None)
        v = snap.values or {}
        status = "awaiting_approval" if pend else (v.get("status") or "done")
        errors = v.get("errors", [])
        recoverable_marketplace_error = any(
            code in error for error in errors for code in ("marketplace_unavailable", "rate_limited")
        )
        degraded = status == "error" and recoverable_marketplace_error and not any(
            v.get(key) for key in ("approval", "submission", "send_result")
        )
        effective = "queued_degraded" if degraded else status
        if status == "error" and not degraded:
            write_may_have_started = any(v.get(key) for key in ("approval", "submission", "send_result"))
            effective = "needs_attention" if write_may_have_started else "dead_letter"
            if effective == "dead_letter":
                self.store.record_dead_letter(run["run_id"], "; ".join(errors) or "run failed without an error detail")
        self.store.update(run["run_id"], status=effective, degraded=degraded)
        return effective, pend

    async def resume(self, run: dict, decision: dict) -> None:
        self._spawn(run, Command(resume=decision))

    async def retry(self, run: dict, user: dict) -> dict:
        """Mid-run crash -> continue from the checkpoint. Finished-with-error (e.g. marketplace was down) -> a fresh
        run of the same target; the failed one is marked superseded so the queue does not grow."""
        snap = await self.graphs[run["kind"]].aget_state(self.cfg(run["run_id"]))
        if snap.next:
            self.store.clear_dead_letter(run["run_id"])
            self._spawn(run, None)
            return run
        self.store.update(run["run_id"], status="superseded", degraded=False)
        return await self.start(user, run["kind"], run["target"])

    async def retry_blocking(self, run_id: str, user: dict) -> dict:
        run = self.store.get(run_id)
        if run is None or run["user_id"] != user["user_id"]:
            raise ValueError(f"unknown run {run_id!r}")
        snap = await self.graphs[run["kind"]].aget_state(self.cfg(run_id))
        if snap.next:
            self.store.clear_dead_letter(run_id)
            self.store.update(run_id, status="running", degraded=False)
            await self._drive(run, None)
            return self.store.get(run_id)
        self.store.update(run_id, status="superseded", degraded=False)
        return await self.run_blocking(user, run["kind"], run["target"])

    async def history(self, run: dict) -> dict:
        graph = self.graphs[run["kind"]]
        items = []
        async for snapshot in graph.aget_state_history(self.cfg(run["run_id"])):
            configurable = (snapshot.config or {}).get("configurable", {})
            items.append({
                "checkpoint_id": configurable.get("checkpoint_id"),
                "step": (snapshot.metadata or {}).get("step"),
                "next": list(snapshot.next),
                "created_at": snapshot.created_at,
            })
        nodes = sorted(set(graph.get_graph().nodes) - {"__start__", "__end__"})
        return {"items": items, "available_nodes": nodes}

    async def _replay_config(
        self, run: dict, checkpoint_id: str, node: str, allow_running: bool = False
    ) -> dict:
        if run["status"] == "running" and not allow_running:
            raise ValueError("a running job cannot be replayed")
        graph = self.graphs[run["kind"]]
        valid_nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
        if node not in valid_nodes:
            raise ValueError(f"unknown graph node {node!r}")
        base_cfg = self.cfg(run["run_id"])
        checkpoint = None
        async for snapshot in graph.aget_state_history(base_cfg):
            if (snapshot.config or {}).get("configurable", {}).get("checkpoint_id") == checkpoint_id:
                checkpoint = snapshot
                break
        if checkpoint is None:
            raise ValueError("checkpoint does not belong to this run")
        return {
            **base_cfg,
            "configurable": {**base_cfg["configurable"], "checkpoint_id": checkpoint_id},
        }

    async def replay(self, run: dict, checkpoint_id: str, node: str) -> dict:
        replay_cfg = await self._replay_config(run, checkpoint_id, node)
        self.store.clear_dead_letter(run["run_id"])
        self._spawn(run, Command(goto=node), replay_cfg)
        return self.store.get(run["run_id"])

    async def replay_blocking(self, run_id: str, checkpoint_id: str, node: str) -> dict:
        run = self.store.get(run_id)
        if run is None:
            raise ValueError(f"unknown run {run_id!r}")
        replay_cfg = await self._replay_config(run, checkpoint_id, node, allow_running=True)
        self.store.clear_dead_letter(run_id)
        self.store.update(run_id, status="running", degraded=False)
        await self._drive(run, Command(goto=node), replay_cfg)
        return self.store.get(run_id)

    async def pending(self, run: dict) -> dict | None:
        snap = await self.graphs[run["kind"]].aget_state(self.cfg(run["run_id"]))
        return next((i.value for t in snap.tasks for i in t.interrupts), None)

    async def values(self, run: dict) -> dict:
        values = (await self.graphs[run["kind"]].aget_state(self.cfg(run["run_id"]))).values or {}
        values = jsonable_encoder(values)
        extra = self.store.extra_usage(run["run_id"])
        if extra:
            values["llm_usage"] = [*(values.get("llm_usage") or []), *extra]
            values["tokens_used"] = int(values.get("tokens_used") or 0) + sum(
                int(call["total_tokens"]) for call in extra
            )
        return values

    async def stream(self, run: dict, after: int = 0):
        rid = run["run_id"]
        i = after
        last_keepalive = time.monotonic()
        while True:
            current = self.store.get(rid) or run
            latest_seq = self.store.last_event_seq(rid)
            events = self.store.events_after(rid, i)
            for ev in events:
                i = ev["seq"]
                yield f"id: {i}\ndata: {json.dumps(ev, default=str)}\n\n"
                if ev["type"] in ("interrupt", "done") and i == latest_seq and current["status"] != "running":
                    return
            if not events and current["status"] not in {"running"}:
                pending = await self.pending(current) if current["status"] == "awaiting_approval" else None
                terminal = (
                    {"type": "interrupt", "payload": pending}
                    if pending else {"type": "done", "status": current["status"]}
                )
                terminal = {**terminal, "seq": i + 1}
                yield f"id: {terminal['seq']}\ndata: {json.dumps(terminal, default=str)}\n\n"
                return
            await asyncio.sleep(0.2)
            if time.monotonic() - last_keepalive >= 30:
                yield ": keep-alive\n\n"
                last_keepalive = time.monotonic()

    async def retry_degraded(self, user: dict) -> int:
        n = 0
        for run in self.store.all_degraded():
            if run["user_id"] == user["user_id"]:       # a user can only requeue their own work
                await self.retry(run, user)
                n += 1
        return n

    async def marketplace_ok(self) -> bool:
        try:
            await asyncio.wait_for(self.deps.port.get_connects_balance(), 5)
            return True
        except Exception:  # noqa: BLE001
            return False
