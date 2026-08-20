"""Registration, login, and the get_current_user dependency every
/chat-family route requires.
"""
from __future__ import annotations

import time

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

# In-memory login/register-attempt tracking. Fine at this app's scale
# (single process, SQLite-backed) -- a multi-process/distributed
# deployment would need this shared (Redis, or a table) instead of
# per-process memory. Plain dicts, not defaultdict: a defaultdict's
# subscript access inserts on *read*, so every unauthenticated request
# with a fresh email/IP would permanently grow these -- unbounded
# pre-auth memory growth. _prune() below deletes a key entirely once its
# bucket empties, so only currently-relevant keys stay resident.
#
# Also note: request.client.host is the direct TCP peer. Behind a
# reverse proxy (e.g. HF Spaces terminating TLS in front of this app)
# that's the proxy's IP, not the end user's, unless uvicorn is run with
# --proxy-headers and a trusted proxy list -- until that's wired up for
# the Phase 2 deploy, every user behind such a proxy shares one IP
# bucket. Not yet an issue locally/in CI, where each client is direct.
_FAILURES_BY_EMAIL: dict[str, list[float]] = {}
_FAILURES_BY_IP: dict[str, list[float]] = {}
_REGISTER_ATTEMPTS_BY_IP: dict[str, list[float]] = {}
# Set once an email crosses RATE_LIMIT_MAX_ATTEMPTS; fixed at that
# moment rather than renewed by further failed attempts. Without this,
# an attacker sending one login failure every <15 minutes keeps a
# victim's fixed window permanently full and the account locked out
# indefinitely -- full elimination of email-keyed lockout abuse needs
# CAPTCHA/2FA (an accepted, documented tradeoff, see docs/SECURITY.md
# row 10); this bounds the damage instead of preventing it entirely.
_LOCKOUT_UNTIL: dict[str, float] = {}

RATE_LIMIT_WINDOW_S = 15 * 60
RATE_LIMIT_MAX_ATTEMPTS = 5
BACKOFF_CAP_S = 300  # 5 minutes -- repeated failures from one IP shouldn't lock it out forever


def _prune(bucket_store: dict[str, list[float]], key: str, now: float) -> list[float]:
    """Returns key's still-valid timestamps, trimming expired ones. Deletes
    the dict entry entirely once its bucket is empty -- see the memory-growth
    note on the module-level dicts above."""
    bucket = bucket_store.get(key)
    if not bucket:
        return []
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_S:
        bucket.pop(0)
    if not bucket:
        del bucket_store[key]
        return []
    return bucket


def _record(bucket_store: dict[str, list[float]], key: str, now: float) -> list[float]:
    bucket = _prune(bucket_store, key, now)
    bucket.append(now)
    bucket_store[key] = bucket
    return bucket


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


# Hashed once at import time and compared against on every login attempt
# for a nonexistent account, so that path costs the same argon2 work as a
# real wrong-password attempt -- otherwise "no such email" returns
# measurably faster than "wrong password", a timing side channel that
# leaks which emails have accounts even though both return the same
# generic message and status code.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-timing-decoy")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_session),  # noqa: B008 -- FastAPI's Depends() is required in the default position
) -> dict:
    now = time.time()
    ip = request.client.host if request.client else "unknown"

    # Every registration call runs an argon2 hash (deliberately expensive
    # and memory-hard) and writes a row -- without this, an unauthenticated
    # attacker gets a cheap CPU/memory exhaustion primitive plus unbounded
    # rows in `users`. Same exponential-backoff mechanism as login's IP
    # limit; counts every attempt (not just failures), since the honeypot
    # path below is the only cheap one and everything past it costs real
    # work regardless of outcome.
    ip_bucket = _prune(_REGISTER_ATTEMPTS_BY_IP, ip, now)
    if ip_bucket and now - ip_bucket[-1] < _backoff_seconds(len(ip_bucket)):
        raise HTTPException(status_code=429, detail="too many registration attempts, try again later")
    _record(_REGISTER_ATTEMPTS_BY_IP, ip, now)

    if req.website:
        # Honeypot tripped: report success without creating anything, so a
        # bot gets no signal distinguishing this from a real registration.
        return {"status": "ok"}

    # Case-fold before storing/looking up -- EmailStr does not normalize
    # case, so without this "Victim@x.com" and "victim@x.com" would be
    # treated as different accounts by both the uniqueness check here and
    # login's rate-limit bucket below.
    email = req.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        # Same generic message as any other rejection here -- never reveal
        # whether a specific email is already registered (that's an
        # enumeration vulnerability: an attacker could otherwise harvest
        # which emails have accounts by probing /auth/register).
        raise HTTPException(status_code=400, detail="email already registered or invalid")

    user = User(email=email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    return {"status": "ok"}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_session)) -> TokenResponse:  # noqa: B008 -- FastAPI's Depends() is required in the default position
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    email = req.email.lower()  # see the register() comment on case-folding

    lockout_until = _LOCKOUT_UNTIL.get(email)
    if lockout_until is not None:
        if lockout_until > now:
            raise HTTPException(status_code=429, detail="too many login attempts, try again later")
        # Lockout window elapsed on its own -- clear it and this email's
        # failure count so this attempt gets a clean slate; a success
        # should not be required to ever reset a lockout.
        del _LOCKOUT_UNTIL[email]
        _FAILURES_BY_EMAIL.pop(email, None)

    ip_bucket = _prune(_FAILURES_BY_IP, ip, now)
    if ip_bucket and now - ip_bucket[-1] < _backoff_seconds(len(ip_bucket)):
        raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    user = db.query(User).filter(User.email == email).first()
    password_ok = verify_password(req.password, user.password_hash if user else _DUMMY_PASSWORD_HASH)

    if not user or not password_ok:
        _record(_FAILURES_BY_IP, ip, now)
        email_bucket = _record(_FAILURES_BY_EMAIL, email, now)
        if len(email_bucket) >= RATE_LIMIT_MAX_ATTEMPTS:
            _LOCKOUT_UNTIL[email] = now + RATE_LIMIT_WINDOW_S
        # Same message whether the email doesn't exist or the password is
        # wrong -- distinguishing the two is another enumeration vector.
        raise HTTPException(status_code=401, detail="invalid email or password")

    # Successful login clears this email's failure history (a user who
    # mistyped their password a few times then got it right shouldn't stay
    # throttled) but deliberately NOT the IP's -- a shared IP (office
    # NAT, campus network) with one honest login and other ongoing failed
    # attempts from elsewhere on that IP shouldn't get a free pass on
    # IP-level throttling from an unrelated success.
    _FAILURES_BY_EMAIL.pop(email, None)

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
