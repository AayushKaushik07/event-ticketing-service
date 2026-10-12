import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role, User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Resolve the caller from the bearer token.

    The user identity comes from here and nowhere else. It is never read from a
    request body, because a client cannot be trusted to say who it is.
    """
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        # `from None` on purpose: the client gets no detail about why the token
        # failed, which would otherwise be an oracle for forging attempts.
        raise _credentials_error from None

    subject = payload.get("sub")
    if subject is None:
        raise _credentials_error

    user = db.get(User, int(subject))
    if user is None:
        # Token is validly signed but the account was deleted since it was issued.
        raise _credentials_error
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """403, not 401: the caller is authenticated, just not permitted."""
    if current_user.role is not Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return current_user
