import sqlite3
import time

import pytest
from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthToken

from apps.api.auth.oauth_store import OAuthVault, UserOAuthStorage


async def test_encrypted_user_tokens_persist_with_expiry_and_no_plaintext(tmp_path):
    db = tmp_path / 'oauth.sqlite'
    key = Fernet.generate_key()
    vault = OAuthVault(db, key)
    store = UserOAuthStorage(vault, 'alice')
    await store.set_tokens(OAuthToken(access_token='private-access-value', refresh_token='private-refresh-value', expires_in=60))
    assert b'private-access-value' not in db.read_bytes()
    assert b'private-refresh-value' not in db.read_bytes()
    assert await UserOAuthStorage(vault, 'bob').get_tokens() is None
    restored = UserOAuthStorage(OAuthVault(db, key), 'alice')
    assert (await restored.get_tokens()).access_token == 'private-access-value'
    record = vault.get('alice', 'tokens')
    record['expires_at'] = time.time() - 10
    vault.put('alice', 'tokens', record)
    assert (await restored.get_tokens()).expires_in == 0
    with sqlite3.connect(db) as connection:
        encrypted = connection.execute('SELECT value FROM oauth WHERE user=?', ('alice',)).fetchone()[0]
        connection.execute('INSERT INTO oauth VALUES (?,?,?)', ('bob', 'tokens', encrypted))
    with pytest.raises(ValueError, match='different user'):
        vault.get('bob', 'tokens')


def test_durable_intent_can_only_be_claimed_once(tmp_path):
    vault = OAuthVault(tmp_path / 'claims.sqlite', Fernet.generate_key())
    assert vault.claim('alice', 'write:key', {'pending': True})
    assert not vault.claim('alice', 'write:key', {'pending': False})
