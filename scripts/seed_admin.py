"""Create the first admin account.

Admins are never created through the API — there is no role field on the
registration endpoint, so nobody can register themselves as one.

    ADMIN_USERNAME=admin ADMIN_PASSWORD='...' python -m scripts.seed_admin

Running it twice is safe: an existing admin with the same username is left
alone rather than overwritten.
"""

import os
import sys

from app.db import SessionLocal
from app.models import Role, User
from app.repository import get_user_by_username
from app.security import hash_password


def main() -> int:
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        print("ADMIN_USERNAME and ADMIN_PASSWORD must be set", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        if get_user_by_username(db, username) is not None:
            print(f"User '{username}' already exists, nothing to do.")
            return 0
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=Role.admin,
            )
        )
        db.commit()
    print(f"Admin '{username}' created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
