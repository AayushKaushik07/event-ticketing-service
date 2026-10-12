from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Role


class RegisterRequest(BaseModel):
    """Self-registration always produces a normal user.

    There is deliberately no `role` field: if a client could send one, anyone
    could register themselves as an admin. Admins are created by the seed script.
    """

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)  # 72 = bcrypt's input limit


class UserOut(BaseModel):
    """Note what is absent: password_hash is never serialised."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
