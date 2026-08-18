"""Registration, login, and the get_current_user dependency every
/chat-family route requires.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from .models import User, get_session
from .security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory login-attempt tracking. Fine at this app's scale (single
# process, SQLite-backed) -- a multi-process/distributed deployment would
# need this shared (Redis, or a table) instead of per-process memory.
_FAILURES_BY_EMAIL: dict[str, list[float]] = defaultdict(list)
_FAILURES_BY_IP: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW_S = 15 * 60
RATE_LIMIT_MAX_ATTEMPTS = 5
BACKOFF_CAP_S = 300  # 5 minutes -- repeated failures from one IP shouldn't lock it out forever


def _prune(bucket: list[float], now: float) -> None:
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_S:
        bucket.pop(0)


def _backoff_seconds(n_recent_failures: int) -> float:
    """Exponential backoff for repeated failures from the same IP: 2, 4, 8,
    16... seconds, capped. n_recent_failures=0 -> 0 (no wait yet)."""
    if n_recent_failures <= 0:
        return 0.0
    return min(2**n_recent_failures, BACKOFF_CAP_S)


class RegisterRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: EmailStr
    password: str = Field(min_length=8)
    # Honeypot: real users and real browsers never populate a field that's
    # visually hidden and has no label a human would fill in. Scripted
    # registration attempts that blindly fill every form field do.
    website: str = Field(default="")


class LoginRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_session)) -> dict:  # noqa: B008 -- FastAPI's Depends() is required in the default position
    if req.website:
        # Honeypot tripped: report success without creating anything, so a
        # bot gets no signal distinguishing this from a real registration.
        return {"status": "ok"}

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        # Same generic message as any other rejection here -- never reveal
        # whether a specific email is already registered (that's an
        # enumeration vulnerability: an attacker could otherwise harvest
        # which emails have accounts by probing /auth/register).
        raise HTTPException(status_code=400, detail="email already registered or invalid")

    user = User(email=req.email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    return {"status": "ok"}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_session)) -> TokenResponse:  # noqa: B008 -- FastAPI's Depends() is required in the default position
    now = time.time()
    ip = request.client.host if request.client else "unknown"

    email_bucket = _FAILURES_BY_EMAIL[req.email]
    ip_bucket = _FAILURES_BY_IP[ip]
    _prune(email_bucket, now)
    _prune(ip_bucket, now)

    if len(email_bucket) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    if ip_bucket:
        wait = _backoff_seconds(len(ip_bucket))
        if now - ip_bucket[-1] < wait:
            raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        email_bucket.append(now)
        ip_bucket.append(now)
        # Same message whether the email doesn't exist or the password is
        # wrong -- distinguishing the two is another enumeration vector.
        raise HTTPException(status_code=401, detail="invalid email or password")

    # Successful login clears this email's failure history (a user who
    # mistyped their password a few times then got it right shouldn't stay
    # throttled) but deliberately NOT the IP's -- a shared IP (office
    # NAT, campus network) with one honest login and other ongoing failed
    # attempts from elsewhere on that IP shouldn't get a free pass on
    # IP-level throttling from an unrelated success.
    email_bucket.clear()

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


class MeResponse(BaseModel):
    email: str
    queries_used: int
    query_limit: int


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_session),  # noqa: B008 -- FastAPI's Depends() is required in the default position
) -> User:
    """FastAPI dependency: `user: User = Depends(get_current_user)`. Verifies
    the JWT server-side and loads the user from the DB by the id encoded in
    it -- never trusts a client-supplied user id from anywhere else."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="not authenticated")
    token = authorization.removeprefix("Bearer ")
    try:
        user_id = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:  # noqa: B008 -- FastAPI's Depends() is required in the default position
    return MeResponse(email=user.email, queries_used=user.queries_used, query_limit=user.query_limit)
