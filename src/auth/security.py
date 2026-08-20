"""Password hashing (argon2 via passlib) and JWT issuance/verification.

JWT_SECRET must be set explicitly in any deployed environment. If
ENV=production and JWT_SECRET is unset, startup fails loudly rather than
silently generating a secret that changes on every process restart and
invalidates every existing session without warning. In development, an
unset secret is fine -- a random one is generated once per process; dev
sessions not surviving a restart is an acceptable, obvious tradeoff, not a
footgun the way it would be in production.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_HOURS = 24
JWT_ALGORITHM = "HS256"

# Generated once per process if JWT_SECRET is unset and ENV != production.
# Deliberately module-level (not regenerated per call) so tokens issued
# earlier in the same process remain verifiable later in that process.
_DEV_SECRET = secrets.token_urlsafe(32)


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if os.environ.get("ENV") == "production":
        raise RuntimeError(
            "JWT_SECRET must be set explicitly when ENV=production -- refusing "
            "to start with an auto-generated secret that would invalidate "
            "every session on the next restart."
        )
    return _DEV_SECRET


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user id encoded in a valid token. Raises
    jose.JWTError (covers ExpiredSignatureError, JWTClaimsError, and a
    tampered/invalid signature) for anything else -- callers should catch
    that one exception type, not enumerate failure modes themselves."""
    payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])
