FUTURE = "2027-01-04T19:30:00Z"
EVENT = {"name": "Konzert", "available_tickets": 2, "event_date": FUTURE}


def test_anonymous_cannot_create_event(client):
    assert client.post("/events", json=EVENT).status_code == 401


def test_normal_user_cannot_create_event(client, user_headers):
    assert client.post("/events", json=EVENT, headers=user_headers).status_code == 403


def test_admin_can_create_event(client, admin_headers):
    r = client.post("/events", json=EVENT, headers=admin_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["total_capacity"] == body["available_tickets"] == 2


def test_past_event_date_is_rejected(client, admin_headers):
    r = client.post(
        "/events",
        json={**EVENT, "event_date": "2020-01-01T00:00:00Z"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_zero_capacity_is_rejected(client, admin_headers):
    r = client.post(
        "/events", json={**EVENT, "available_tickets": 0}, headers=admin_headers
    )
    assert r.status_code == 422


def test_listing_events_is_public(client):
    assert client.get("/events").status_code == 200


def test_delete_unknown_event_returns_404(client, admin_headers):
    assert client.delete("/events/999999", headers=admin_headers).status_code == 404


def test_normal_user_cannot_delete(client, admin_headers, user_headers):
    eid = client.post("/events", json=EVENT, headers=admin_headers).json()["id"]
    assert client.delete(f"/events/{eid}", headers=user_headers).status_code == 403


def test_deleting_event_cascades_to_bookings(client, admin_headers, user_headers):
    eid = client.post("/events", json=EVENT, headers=admin_headers).json()["id"]
    client.post("/tickets", json={"event_id": eid}, headers=user_headers)
    assert len(client.get("/tickets/me", headers=user_headers).json()) == 1

    assert client.delete(f"/events/{eid}", headers=admin_headers).status_code == 204
    assert client.get("/tickets/me", headers=user_headers).json() == []
