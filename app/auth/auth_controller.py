from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.auth_schemas import RegisterRequest, TokenResponse, UserOut
from app.auth.auth_service import AuthService
from app.db import get_db
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    """Create a normal user account. 409 if the username is taken."""
    return service.register(payload.username, payload.password)


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    """Exchange username and password for a JWT.

    Uses OAuth2PasswordRequestForm (form-encoded, not JSON) so the Authorize
    button in the generated Swagger UI works against this endpoint directly.
    """
    token = service.login(form.username, form.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Who the current token belongs to."""
    return current_user
