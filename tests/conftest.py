import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://ticketing:ticketing@localhost:3306/ticketing_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-production")

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import hash_password  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], future=True)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

ADMIN = ("admin", "adminpass123")
USER = ("alice", "password123")


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """TRUNCATE is blocked by foreign keys in MySQL, so constraint checking is
    switched off for the duration of the cleanup. This is a test-only shortcut;
    it never runs against a real database."""
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in ("bookings", "events", "users"):
            conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    yield


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_users(db):
    db.add_all(
        [
            User(username=ADMIN[0], password_hash=hash_password(ADMIN[1]), role=Role.admin),
            User(username=USER[0], password_hash=hash_password(USER[1]), role=Role.user),
        ]
    )
    db.commit()


def auth_header(client, username: str, password: str) -> dict:
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client, seeded_users):
    return auth_header(client, *ADMIN)


@pytest.fixture
def user_headers(client, seeded_users):
    return auth_header(client, *USER)
