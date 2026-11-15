"""Transactional local mock state, owned exclusively by the Workspace MCP server."""
import json
import sqlite3
from pathlib import Path

from mcp_servers.workspace.tools import WorkspaceService


class PersistentWorkspaceService:
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, state TEXT NOT NULL)')

    async def _call(self, operation, *args):
        db = sqlite3.connect(self.database, timeout=15)
        try:
            db.execute('BEGIN IMMEDIATE')
            svc = WorkspaceService()
            row = db.execute('SELECT state FROM workspace WHERE id=1').fetchone()
            if row:
                saved = json.loads(row[0])
                svc.holds, svc.emails = saved['holds'], saved['emails']
            result = await getattr(svc, operation)(*args)
            db.execute('INSERT INTO workspace VALUES (1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state',
                       (json.dumps({'holds': svc.holds, 'emails': svc.emails}),))
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    async def get_free_slots(self, start_date, days=5, duration_minutes=30, limit=5):
        return await self._call('get_free_slots', start_date, days, duration_minutes, limit)

    async def create_tentative_hold(self, start, title, idempotency_key):
        return await self._call('create_tentative_hold', start, title, idempotency_key)

    async def create_email_draft(self, to, subject, body, idempotency_key):
        return await self._call('create_email_draft', to, subject, body, idempotency_key)
