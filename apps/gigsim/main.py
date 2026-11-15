"""Persistent, authenticated GigSim REST service owned by this project."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.marketplace_port import MarketplaceError
from mcp_servers.marketplace.adapters.localsim import LocalSimAdapter
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.tools import ProposalInput

ROOT = Path(__file__).resolve().parents[2]


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal: dict
    key: str = Field(min_length=8, max_length=128)
    preview: bool = False


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(min_length=8, max_length=128)


class MessageRequest(WriteRequest):
    text: str = Field(min_length=1, max_length=5000)


class Simulator:
    def __init__(self, data_dir, database, connects=100, seed=7):
        self.data_dir, self.database = Path(data_dir), Path(database)
        self.connects, self.seed = connects, seed
        if connects < 0:
            raise ValueError('Initial Connects must be nonnegative')
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def adapter(self):
        # Reuse the documented scoring model; never expose private preferences through REST/MCP.
        a = LocalSimAdapter.__new__(LocalSimAdapter)
        SampleAdapter.__init__(a, self.data_dir, self.connects)
        a.seed = self.seed
        path = self.data_dir / 'hidden_prefs.json'
        a._hidden = json.loads(path.read_text()) if path.exists() else {
            key: {'must_have': job.get('required_skills', []),
                  'budget_ceiling': None, 'dislikes_generic': True} for key, job in a._jobs.items()}
        return a

    def call(self, account, operation, args):
        db = sqlite3.connect(self.database, timeout=30)
        try:
            # Serializes the entire read/modify/write cycle, including multiple processes.
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM accounts WHERE id=?', (account,)).fetchone()
            a = self.adapter()
            saved = json.loads(row[0]) if row else {}
            for field in ['balance', 'drafts', 'submissions', 'sent', 'audit', '_threads']:
                if field in saved:
                    setattr(a, field, saved[field])
            fingerprints = saved.get('fingerprints', {})
            key = args.get('idempotency_key')
            slot = f'{operation}:{key}'
            digest = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
            preview = args.get('dry_run', False)
            if key and not preview and slot in fingerprints and fingerprints[slot] != digest:
                raise MarketplaceError('idempotency_conflict')
            if operation == 'submit_proposal':
                prior = next((v for v in a.submissions.values() if v['draft_id'] == args['draft_id']), None)
                if prior:
                    result = {**prior, 'replayed': True}
                else:
                    result = asyncio.run(a.submit_proposal(**args))
            elif operation == 'outcomes':
                result = []
                for submission in a.submissions.values():
                    draft_key = next(k for k, d in a.drafts.items() if d['draft_id'] == submission['draft_id'])
                    outcome = a.outcome_for(draft_key)
                    result.append({'draft_id': submission['draft_id'],
                                   **{k: outcome[k] for k in ['replied', 'interview', 'hired']},
                                   'source': 'synthetic-rule-based-client'})
            else:
                result = asyncio.run(getattr(a, operation)(**args))
            if key and not preview:
                fingerprints[slot] = digest
            state = {f: getattr(a, f) for f in ['balance', 'drafts', 'submissions', 'sent', 'audit', '_threads']}
            state['fingerprints'] = fingerprints
            db.execute('INSERT INTO accounts VALUES (?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state',
                       (account, json.dumps(state)))
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def create_app(data_dir=None, database=None, tokens=None, connects=None, seed=7):
    tokens = tokens if tokens is not None else json.loads(os.environ.get('GIGSIM_TOKENS_JSON', '{}'))
    if not tokens or any(not k or not isinstance(v, str) or not v for k, v in tokens.items()):
        raise ValueError('Configure GIGSIM_TOKENS_JSON as a nonempty token-to-account JSON mapping')
    simulator = Simulator(data_dir or os.environ.get('GIGBID_DATA_DIR', ROOT / 'data/processed/kaggle_2024_v1'),
                          database or os.environ.get('GIGSIM_DB', ROOT / '.local-models/gigsim/state.sqlite'),
                          int(os.environ.get('GIGSIM_CONNECTS', '100')) if connects is None else connects, seed)
    app = FastAPI(title='GigBid GigSim', version='1.0.0',
                  description='Project-owned synthetic marketplace. Outcomes are simulated, not real hiring results.')
    app.state.simulator = simulator

    @app.middleware('http')
    async def authenticate(request: Request, next_handler):
        if request.url.path == '/health':
            return await next_handler(request)
        bearer = request.headers.get('authorization', '')
        account = next((v for k, v in tokens.items() if hmac.compare_digest(bearer, f'Bearer {k}')), None)
        if account is None:
            return JSONResponse({'code': 'unauthorized'}, status_code=401)
        request.state.account = account
        return await next_handler(request)

    @app.exception_handler(MarketplaceError)
    async def marketplace_error(request, error):
        status = 404 if error.code.endswith('_not_found') else 409 if error.code in {'insufficient_connects', 'idempotency_conflict'} else 400
        return JSONResponse({'code': error.code}, status_code=status)

    def call(request, operation, **args):
        return simulator.call(request.state.account, operation, args)

    def check_key(body, header):
        if header != body.key:
            raise HTTPException(400, 'Idempotency-Key must match request key')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': 'gigbid-gigsim', 'synthetic': True}

    @app.get('/v1/jobs')
    def jobs(request: Request, q: Annotated[str | None, Query(max_length=200)] = None,
             limit: Annotated[int, Query(ge=1, le=100)] = 20):
        return {'jobs': call(request, 'search_jobs', query=q, limit=limit)}

    @app.get('/v1/jobs/{job_id}')
    def job(request: Request, job_id: str):
        return call(request, 'get_job', job_id=job_id)

    @app.get('/v1/clients/{client_id}')
    def client(request: Request, client_id: str):
        return call(request, 'get_client_history', client_id=client_id)

    @app.get('/v1/balance')
    def balance(request: Request):
        return call(request, 'get_connects_balance')

    @app.post('/v1/drafts')
    def draft(request: Request, body: DraftRequest, idempotency_key: str = Header()):
        check_key(body, idempotency_key)
        # Validate the same proposal schema as MCP, allowing namespaced HTTP keys.
        try:
            validated = ProposalInput.model_validate({**body.proposal, 'idempotency_key': 'validation-key', 'dry_run': body.preview})
        except ValidationError as error:
            raise HTTPException(422, 'Invalid proposal fields') from error
        payload = validated.model_dump(exclude={'idempotency_key', 'dry_run'}, exclude_none=True)
        return call(request, 'create_proposal_draft', payload=payload, idempotency_key=body.key, dry_run=body.preview)

    @app.post('/v1/drafts/{draft_id}/submit')
    def submit(request: Request, draft_id: str, body: WriteRequest, idempotency_key: str = Header()):
        check_key(body, idempotency_key)
        return call(request, 'submit_proposal', draft_id=draft_id, idempotency_key=body.key)

    @app.get('/v1/threads')
    def threads(request: Request):
        return {'threads': call(request, 'list_threads')}

    @app.get('/v1/threads/{thread_id}')
    def messages(request: Request, thread_id: str):
        return call(request, 'list_messages', thread_id=thread_id)

    @app.post('/v1/threads/{thread_id}/messages')
    def send(request: Request, thread_id: str, body: MessageRequest, idempotency_key: str = Header()):
        check_key(body, idempotency_key)
        return call(request, 'send_message', thread_id=thread_id, text=body.text, idempotency_key=body.key)

    @app.get('/v1/outcomes')
    def outcomes(request: Request):
        return {'outcomes': call(request, 'outcomes')}

    return app
