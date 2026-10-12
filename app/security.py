from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

# bcrypt hashes at most 72 bytes of input and silently ignores the rest, so the
# registration schema caps passwords at 72 characters rather than letting a long
# password be truncated without the user knowing.
BCRYPT_MAX_BYTES = 72


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),          # JWT spec requires 'sub' to be a string
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError (or a subclass) on any invalid token.

    Passing algorithms= explicitly is not optional: accepting the algorithm from
    the token header is the classic JWT 'alg: none' vulnerability.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
