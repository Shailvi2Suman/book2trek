"""Tool tests — the agent's tools driven through the in-process Flask transport."""
from book2trek.agent import tools as T
from book2trek.rag.knowledge import build_kb


def _client(app):
    c = T.ApiClient(T.FlaskTransport(app))
    assert c.login("user@example.com", "pw")
    return c


def test_search_tool_speech(app):
    c = _client(app)
    out = T.search_treks(c, query="manali")
    assert out["results"] and "trek" in out["speech"].lower()


def test_availability_tool(app):
    c = _client(app)
    out = T.check_availability(c, 1)
    assert "slots" in out["speech"].lower()


def test_book_and_cancel_flow(app):
    c = _client(app)
    booked = T.book_trek(c, 1)
    assert "booked" in booked["speech"].lower()
    bid = booked["booking_id"]
    mine = T.list_my_bookings(c)
    assert any(b["id"] == bid for b in mine["bookings"])
    cancelled = T.cancel_booking(c, bid)
    assert "cancel" in cancelled["speech"].lower()


def test_book_full_trek_speaks_error(app):
    c = _client(app)
    out = T.book_trek(c, 2)   # Triund is full
    assert "couldn't book" in out["speech"].lower()


def test_answer_faq_tool(app):
    kb = build_kb()
    out = T.answer_faq(kb, "what is your cancellation policy")
    assert "cancel" in out["speech"].lower()
    assert out["sources"]
