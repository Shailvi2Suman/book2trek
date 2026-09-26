"""
Agent tools — the functions the LLM can call, wired to the /api layer + RAG.

Kept free of any LiveKit dependency so they're plain, unit-testable functions.
Each returns a short, speakable result (the voice agent reads it back via TTS).

The API is reached through a pluggable Transport:
  * RequestsTransport — real HTTP (production, against a running API).
  * FlaskTransport    — an in-process Flask test client (tests, no server/keys).
Same tool code runs both ways.
"""
from __future__ import annotations

from typing import Protocol

from .. import config as C


class Transport(Protocol):
    def request(self, method: str, path: str, *, params=None,
                json=None, headers=None) -> tuple[int, dict]: ...


class RequestsTransport:  # pragma: no cover - needs a running API
    def __init__(self, base_url: str = C.API_BASE_URL) -> None:
        import requests
        self._requests = requests
        self.base_url = base_url.rstrip("/")

    def request(self, method, path, *, params=None, json=None, headers=None):
        resp = self._requests.request(
            method, f"{self.base_url}{path}", params=params, json=json,
            headers=headers, timeout=10)
        try:
            body = resp.json()
        except Exception:
            body = {}
        return resp.status_code, body


class FlaskTransport:
    """Wrap a Flask test client so tools run in-process without a server."""

    def __init__(self, app) -> None:
        self._client = app.test_client()

    def request(self, method, path, *, params=None, json=None, headers=None):
        resp = self._client.open(path, method=method, query_string=params,
                                 json=json, headers=headers)
        return resp.status_code, (resp.get_json(silent=True) or {})


class ApiClient:
    """Thin client the tools share; holds the JWT after login."""

    def __init__(self, transport: Transport) -> None:
        self.t = transport
        self.token: str | None = None

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, email: str, password: str) -> bool:
        code, body = self.t.request("POST", "/api/auth/login",
                                    json={"email": email, "password": password})
        if code == 200:
            self.token = body["access_token"]
            return True
        return False

    def get(self, path, params=None):
        return self.t.request("GET", path, params=params, headers=self._auth())

    def post(self, path, json=None):
        return self.t.request("POST", path, json=json, headers=self._auth())


# --------------------------------------------------------------------------
# The tools (LLM-callable). Each returns a dict; the agent verbalises `speech`.
# --------------------------------------------------------------------------
def search_treks(client: ApiClient, query: str = "", location: str = "",
                 difficulty: str = "") -> dict:
    """Find open treks by keyword, location, or difficulty."""
    _, body = client.get("/api/treks/search",
                         {"q": query, "location": location, "difficulty": difficulty})
    results = body.get("results", [])
    if not results:
        return {"results": [], "speech": "I couldn't find any open treks for that."}
    names = ", ".join(f"{r['name']} in {r['location']} ({r['available_slots']} slots)"
                      for r in results[:3])
    return {"results": results,
            "speech": f"I found {len(results)} treks. Top picks: {names}."}


def check_availability(client: ApiClient, trek_id: int) -> dict:
    """Check if a specific trek is bookable right now."""
    code, body = client.get(f"/api/treks/{trek_id}/availability")
    if code != 200:
        return {"speech": "I couldn't find that trek."}
    if body.get("bookable"):
        return {**body, "speech": f"{body['name']} has {body['available_slots']} slots open."}
    return {**body, "speech": f"Sorry, {body['name']} isn't available for booking."}


def book_trek(client: ApiClient, trek_id: int) -> dict:
    """Book a trek for the logged-in user (confirm high-stakes actions first)."""
    code, body = client.post("/api/bookings", {"trek_id": trek_id})
    if code == 201:
        return {**body, "speech": f"Booked {body['trek']}. You're all set!"}
    return {**body, "speech": f"I couldn't book that: {body.get('error', 'unknown error')}."}


def list_my_bookings(client: ApiClient) -> dict:
    """List the user's current bookings."""
    _, body = client.get("/api/bookings")
    rows = body.get("bookings", [])
    if not rows:
        return {"bookings": [], "speech": "You don't have any bookings yet."}
    active = [b for b in rows if b["status"] == "Booked"]
    speech = "Your booked treks: " + ", ".join(b["trek"] for b in active) \
        if active else "You have no active bookings."
    return {"bookings": rows, "speech": speech}


def cancel_booking(client: ApiClient, booking_id: int) -> dict:
    """Cancel one of the user's bookings by id (idempotent server-side)."""
    code, body = client.post(f"/api/bookings/{booking_id}/cancel")
    if code == 200:
        return {**body, "speech": "Your booking is cancelled."}
    return {**body, "speech": f"I couldn't cancel that: {body.get('error', 'unknown error')}."}


def answer_faq(kb, question: str) -> dict:
    """Answer a policy / info question from the RAG knowledge base."""
    from ..rag.knowledge import answer_question
    res = answer_question(kb, question)
    return {**res, "speech": res["answer"]}
