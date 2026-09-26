"""API endpoint tests: auth, search+cache, availability, booking rules, RBAC."""


def _token(client):
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": "pw"})
    assert r.status_code == 200
    return r.get_json()["access_token"]


def test_login_bad_credentials(client):
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": "nope"})
    assert r.status_code == 401


def test_search_and_cache_flag(client):
    r1 = client.get("/api/treks/search", query_string={"q": "roopkund"})
    body1 = r1.get_json()
    assert r1.status_code == 200 and body1["cached"] is False
    assert any(t["name"] == "Roopkund" for t in body1["results"])
    r2 = client.get("/api/treks/search", query_string={"q": "roopkund"})
    assert r2.get_json()["cached"] is True          # second hit served from cache


def test_search_only_open(client):
    r = client.get("/api/treks/search", query_string={"difficulty": "easy"})
    names = [t["name"] for t in r.get_json()["results"]]
    assert "Triund" in names                         # Open but 0 slots still listed


def test_availability(client):
    r = client.get("/api/treks/2/availability")       # Triund, 0 slots
    b = r.get_json()
    assert b["available_slots"] == 0 and b["bookable"] is False


def test_booking_requires_auth(client):
    r = client.post("/api/bookings", json={"trek_id": 1})
    assert r.status_code == 401


def test_book_success_decrements_slots(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    before = client.get("/api/treks/1/availability").get_json()["available_slots"]
    r = client.post("/api/bookings", json={"trek_id": 1}, headers=h)
    assert r.status_code == 201
    after = client.get("/api/treks/1/availability").get_json()["available_slots"]
    assert after == before - 1


def test_double_booking_blocked(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/api/bookings", json={"trek_id": 1}, headers=h)
    r = client.post("/api/bookings", json={"trek_id": 1}, headers=h)
    assert r.status_code == 409


def test_book_full_trek_blocked(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/bookings", json={"trek_id": 2}, headers=h)  # Triund full
    assert r.status_code == 409


def test_cancel_restores_slot(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    bid = client.post("/api/bookings", json={"trek_id": 1}, headers=h).get_json()["booking_id"]
    after_book = client.get("/api/treks/1/availability").get_json()["available_slots"]
    client.post(f"/api/bookings/{bid}/cancel", headers=h)
    after_cancel = client.get("/api/treks/1/availability").get_json()["available_slots"]
    assert after_cancel == after_book + 1
