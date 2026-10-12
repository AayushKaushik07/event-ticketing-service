from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import repository
from app.errors import InvalidCredentialsError, UsernameTakenError
from app.models import Role, User
from app.security import create_access_token, hash_password, verify_password


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def register(self, username: str, password: str) -> User:
        if repository.get_user_by_username(self._db, username) is not None:
            raise UsernameTakenError(username)

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=Role.user,   # never taken from the request
        )
        try:
            repository.add_user(self._db, user)   # flush: the INSERT happens here
            self._db.commit()
        except IntegrityError:
            # Two concurrent registrations can both pass the check above; the
            # UNIQUE constraint on username decides, and the loser gets a 409
            # instead of a 500.
            self._db.rollback()
            raise UsernameTakenError(username) from None
        self._db.refresh(user)
        return user

    def login(self, username: str, password: str) -> str:
        user = repository.get_user_by_username(self._db, username)
        # Same error for unknown user and wrong password, so the endpoint cannot
        # be used to discover which usernames exist.
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return create_access_token(user_id=user.id, role=user.role.value)
