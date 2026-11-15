from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.deps import get_user
from apps.api.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, request: Request):
    users = request.app.state.users
    try:
        u = users.create(body.email, body.password, body.freelancer_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return TokenOut(token=users.issue(u["user_id"]), user=UserOut(**u))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request):
    users = request.app.state.users
    u = users.login(body.email, body.password)
    if not u:
        raise HTTPException(401, "invalid credentials")
    return TokenOut(token=users.issue(u["user_id"]), user=UserOut(**u))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_user)):
    return UserOut(**user)


@router.get("/personas")
def personas(request: Request):
    """Public: personas a new user can choose at onboarding (synthetic freelancer profiles)."""
    return [{"freelancer_id": k, "display_name": v["display_name"], "hourly_rate_usd": v["hourly_rate_usd"]}
            for k, v in request.app.state.users._personas.items()]
