
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from apps.api.deps import get_user

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsIn(BaseModel):
    hourly_rate_usd: float | None = Field(None, gt=0, le=1000)
    minimum_project_budget_usd: float | None = Field(None, ge=0, le=1_000_000)
    weekly_connects_budget: int | None = Field(None, ge=0, le=1000)
    auto_skip_low_fit: bool | None = None          # autonomy: may auto-skip, never auto-send


class SettingsOut(SettingsIn):
    saved_searches: list[str] = []
    autonomy_note: str = "GigBid never sends a proposal or message without your approval."


def _out(request: Request, user: dict) -> SettingsOut:
    st = request.app.state.manager.store
    return SettingsOut(**st.get_settings(user["user_id"]), saved_searches=[q for _, q in st.searches(user["user_id"])])


@router.get("", response_model=SettingsOut)
def get_settings(request: Request, user: dict = Depends(get_user)):
    return _out(request, user)


@router.put("", response_model=SettingsOut)
def put_settings(body: SettingsIn, request: Request, user: dict = Depends(get_user)):
    st = request.app.state.manager.store
    st.put_settings(user["user_id"], {**st.get_settings(user["user_id"]), **body.model_dump(exclude_none=True)})
    return _out(request, user)


@router.post("/searches/{query}", response_model=SettingsOut)
def add_search(query: str, request: Request, user: dict = Depends(get_user)):
    request.app.state.manager.store.add_search(user["user_id"], query[:200])
    return _out(request, user)


@router.delete("/searches/{query}", response_model=SettingsOut)
def remove_search(query: str, request: Request, user: dict = Depends(get_user)):
    request.app.state.manager.store.remove_search(user["user_id"], query)
    return _out(request, user)
