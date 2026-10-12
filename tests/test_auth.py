def test_register_creates_a_normal_user(client):
    r = client.post("/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["role"] == "user"
    assert "password_hash" not in r.json()


def test_cannot_self_register_as_admin(client):
    """An extra `role` field is ignored, not honoured."""
    r = client.post(
        "/auth/register",
        json={"username": "mallory", "password": "password123", "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "user"


def test_duplicate_username_returns_409(client):
    client.post("/auth/register", json={"username": "bob", "password": "password123"})
    r = client.post("/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 409


def test_wrong_password_returns_401(client, seeded_users):
    r = client.post("/auth/login", data={"username": "alice", "password": "nope"})
    assert r.status_code == 401


def test_unknown_user_and_wrong_password_are_indistinguishable(client, seeded_users):
    a = client.post("/auth/login", data={"username": "alice", "password": "nope"})
    b = client.post("/auth/login", data={"username": "ghost", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_garbage_token_is_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
