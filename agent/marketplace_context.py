"""Application user and explicit graph approval, isolated across concurrent async tasks."""
from contextvars import ContextVar

marketplace_user: ContextVar[str | None] = ContextVar('marketplace_user', default=None)
approved_write: ContextVar[bool] = ContextVar('approved_marketplace_write', default=False)
