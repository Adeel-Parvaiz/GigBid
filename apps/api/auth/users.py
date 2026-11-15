"""Multi-user auth: PBKDF2 passwords, signed expiring session tokens. Every query is scoped by user_id."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from agent.runtime import DATA
from apps.api.storage import serialized


def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


class UserStore:
    def __init__(self, db: str = ":memory:", secret: str | None = None):
        self._db_lock = RLock()
        self.db = sqlite3.connect(db, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY, email TEXT UNIQUE,
                           pw_hash TEXT, salt TEXT, freelancer_id TEXT)""")
        self.tokens = URLSafeTimedSerializer(secret or os.environ.get("APP_SECRET_KEY") or secrets.token_hex(16), salt="session")
        self._personas = {r["freelancer_id"]: r for r in json.loads((Path(DATA) / "freelancers.json").read_text())}

    def persona(self, freelancer_id: str) -> dict:
        return self._personas[freelancer_id]

    @serialized
    def create(self, email: str, password: str, freelancer_id: str) -> dict:
        if freelancer_id not in self._personas:
            raise ValueError("unknown persona")
        salt, uid = secrets.token_hex(16), uuid.uuid4().hex[:12]
        try:
            self.db.execute("INSERT INTO users VALUES (?,?,?,?,?)", (uid, email.lower(), _hash(password, salt), salt, freelancer_id))
        except sqlite3.IntegrityError as e:
            raise ValueError("email already registered") from e
        self.db.commit()
        return self.get(uid)  # type: ignore[return-value]

    @serialized
    def get(self, uid: str) -> dict | None:
        r = self.db.execute("SELECT user_id,email,freelancer_id FROM users WHERE user_id=?", (uid,)).fetchone()
        return {"user_id": r[0], "email": r[1], "freelancer_id": r[2],
                "display_name": self._personas[r[2]]["display_name"]} if r else None

    @serialized
    def login(self, email: str, password: str) -> dict | None:
        r = self.db.execute("SELECT user_id,pw_hash,salt FROM users WHERE email=?", (email.lower(),)).fetchone()
        if r and hmac.compare_digest(r[1], _hash(password, r[2])):
            return self.get(r[0])
        return None

    def issue(self, uid: str) -> str:
        return self.tokens.dumps({"uid": uid})

    def verify(self, token: str, max_age: int = 86400) -> dict | None:
        try:
            return self.get(self.tokens.loads(token, max_age=max_age)["uid"])
        except (BadSignature, SignatureExpired):
            return None


_ = time
