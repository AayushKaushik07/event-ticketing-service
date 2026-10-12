FUTURE = "2027-01-04T19:30:00Z"


def make_event(client, admin_headers, seats=2):
    r = client.post(
        "/events",
        json={"name": "Konzert", "available_tickets": seats, "event_date": FUTURE},
        headers=admin_headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_booking_requires_authentication(client, admin_headers):
    eid = make_event(client, admin_headers)
    assert client.post("/tickets", json={"event_id": eid}).status_code == 401


def test_booking_uses_the_token_identity(client, admin_headers, user_headers, db):
    """The booking belongs to the caller even though no user id was sent."""
    from app.models import User

    eid = make_event(client, admin_headers)
    r = client.post("/tickets", json={"event_id": eid}, headers=user_headers)
    assert r.status_code == 201

    alice = db.query(User).filter_by(username="alice").one()
    assert r.json()["user_id"] == alice.id


def test_sold_out_returns_400(client, admin_headers, user_headers):
    eid = make_event(client, admin_headers, seats=1)
    assert client.post("/tickets", json={"event_id": eid}, headers=user_headers).status_code == 201
    assert client.post("/tickets", json={"event_id": eid}, headers=user_headers).status_code == 400


def test_booking_unknown_event_returns_404(client, user_headers):
    r = client.post("/tickets", json={"event_id": 999999}, headers=user_headers)
    assert r.status_code == 404


def test_users_only_see_their_own_tickets(client, admin_headers, user_headers):
    eid = make_event(client, admin_headers, seats=5)
    client.post("/tickets", json={"event_id": eid}, headers=user_headers)
    client.post("/tickets", json={"event_id": eid}, headers=admin_headers)

    assert len(client.get("/tickets/me", headers=user_headers).json()) == 1
    assert len(client.get("/tickets/me", headers=admin_headers).json()) == 1


def test_booking_count_is_admin_only(client, admin_headers, user_headers):
    eid = make_event(client, admin_headers)
    assert client.get(f"/tickets/count?event_id={eid}", headers=user_headers).status_code == 403
    assert client.get(f"/tickets/count?event_id={eid}", headers=admin_headers).status_code == 200


def test_counter_matches_booking_rows(client, admin_headers, user_headers):
    """Drift detector: `available` comes from the counter on the event,
    `booked` from counting rows. If these ever disagree, a code path is writing
    bookings without going through book_ticket."""
    eid = make_event(client, admin_headers, seats=5)
    for _ in range(3):
        client.post("/tickets", json={"event_id": eid}, headers=user_headers)

    body = client.get(f"/tickets/count?event_id={eid}", headers=admin_headers).json()
    assert body["booked"] == 3
    assert body["available"] == 2
    assert body["booked"] + body["available"] == body["total_capacity"]
