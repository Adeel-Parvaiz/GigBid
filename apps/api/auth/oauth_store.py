"""Encrypted per-user OAuth state. Secrets are never returned through the application API."""
import json
import os
import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class OAuthVault:
    def __init__(self, database=None, key=None):
        root = Path(__file__).resolve().parents[3]
        self.database = Path(database or os.environ.get('OAUTH_DB', root / '.local-models/oauth/tokens.sqlite'))
        self.database.parent.mkdir(parents=True, exist_ok=True)
        key = key or os.environ.get('OAUTH_ENCRYPTION_KEY')
        if not key:
            path = self.database.with_suffix('.key')
            if not path.exists():
                if self.database.exists() and self.database.stat().st_size:
                    raise ValueError('OAuth encryption key missing; restore the original key instead of replacing it')
                try:
                    with path.open('xb') as f:
                        path.chmod(0o600)
                        f.write(Fernet.generate_key())
                except FileExistsError:
                    pass
            key = path.read_bytes()
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS oauth(user TEXT, kind TEXT, value BLOB, PRIMARY KEY(user,kind))')

    def get(self, user, kind, default=None):
        with sqlite3.connect(self.database) as db:
            row = db.execute('SELECT value FROM oauth WHERE user=? AND kind=?', (user, kind)).fetchone()
        if not row:
            return default
        record = json.loads(self.cipher.decrypt(row[0]))
        if record['user'] != user or record['kind'] != kind:
            raise ValueError('Encrypted OAuth record belongs to a different user or purpose')
        return record['data']

    def put(self, user, kind, data):
        encrypted = self.cipher.encrypt(json.dumps({'user': user, 'kind': kind, 'data': data}).encode())
        with sqlite3.connect(self.database) as db:
            db.execute('INSERT INTO oauth VALUES (?,?,?) ON CONFLICT(user,kind) DO UPDATE SET value=excluded.value', (user, kind, encrypted))

    def claim(self, user, kind, data):
        encrypted = self.cipher.encrypt(json.dumps({'user': user, 'kind': kind, 'data': data}).encode())
        with sqlite3.connect(self.database) as db:
            return db.execute('INSERT OR IGNORE INTO oauth VALUES (?,?,?)', (user, kind, encrypted)).rowcount == 1

    def delete(self, user, kind):
        with sqlite3.connect(self.database) as db:
            db.execute('DELETE FROM oauth WHERE user=? AND kind=?', (user, kind))

    def list_prefix(self, user, prefix):
        with sqlite3.connect(self.database) as db:
            kinds = [r[0] for r in db.execute('SELECT kind FROM oauth WHERE user=? AND substr(kind,1,?)=?', (user, len(prefix), prefix))]
        return [self.get(user, kind) for kind in kinds]


class UserOAuthStorage:
    """MCP SDK TokenStorage, bound to one application user."""
    def __init__(self, vault, user):
        self.vault, self.user = vault, user

    async def get_tokens(self):
        record = self.vault.get(self.user, 'tokens')
        if not record:
            return None
        token = dict(record['token'])
        if record.get('expires_at') is not None:
            token['expires_in'] = max(0, int(record['expires_at'] - time.time()))
        return OAuthToken.model_validate(token)

    async def set_tokens(self, tokens):
        self.vault.put(self.user, 'tokens', {'token': tokens.model_dump(mode='json'),
                      'expires_at': time.time() + tokens.expires_in if tokens.expires_in is not None else None})

    async def get_client_info(self):
        info = self.vault.get(self.user, 'client')
        return OAuthClientInformationFull.model_validate(info) if info else None

    async def set_client_info(self, client_info):
        self.vault.put(self.user, 'client', client_info.model_dump(mode='json'))
