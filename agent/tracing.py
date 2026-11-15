"""One trace id flows UI request -> API -> graph -> MCP servers -> audit log (E3)."""
import contextvars
import uuid

current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace_id", default="-")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]
