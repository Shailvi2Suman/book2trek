"""
REST API blueprint (/api/*) layered on the existing Flask app.

These are the endpoints the voice agent's tools call. They reuse the SAME
models and booking rules as the server-rendered app, so voice bookings and
web bookings can never diverge — one source of truth for availability.

Endpoints:
    POST /api/auth/login                 -> { access_token }
    GET  /api/treks/search?q=&location=&difficulty=   (cached)
    GET  /api/treks/<id>/availability
    POST /api/bookings         {trek_id}      (user)   -> book, async notify
    GET  /api/bookings                        (user)   -> my bookings
    POST /api/bookings/<id>/cancel            (user)   -> cancel
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

from models import Booking, Trek, User, db

from .auth import create_token, jwt_required
from .cache import cache_get_json, cache_set_json
from .tasks import send_booking_notification

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _trek_json(t: Trek) -> dict:
    return {
        "id": t.id, "name": t.name, "location": t.location,
        "difficulty": t.difficulty, "duration_days": t.duration_days,
        "available_slots": t.available_slots, "status": t.status,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "description": t.description,
    }


@api_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(error="invalid credentials"), 401
    if user.status == "blacklisted":
        return jsonify(error="account blacklisted"), 403
    return jsonify(access_token=create_token(user.id, user.role), role=user.role)


@api_bp.get("/treks/search")
def search_treks():
    q = (request.args.get("q") or "").strip().lower()
    location = (request.args.get("location") or "").strip().lower()
    difficulty = (request.args.get("difficulty") or "").strip().lower()

    key = f"treks:search:{q}|{location}|{difficulty}"
    cached = cache_get_json(key)
    if cached is not None:
        return jsonify(results=cached, cached=True)

    query = Trek.query.filter(Trek.status == "Open")
    if q:
        query = query.filter(
            db.or_(Trek.name.ilike(f"%{q}%"), Trek.location.ilike(f"%{q}%")))
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))
    if difficulty:
        query = query.filter(Trek.difficulty.ilike(difficulty))

    results = [_trek_json(t) for t in query.order_by(Trek.start_date).limit(20)]
    cache_set_json(key, results)
    return jsonify(results=results, cached=False)


@api_bp.get("/treks/<int:trek_id>/availability")
def availability(trek_id: int):
    t = db.session.get(Trek, trek_id)
    if not t:
        return jsonify(error="trek not found"), 404
    return jsonify(
        trek_id=t.id, name=t.name, status=t.status,
        available_slots=t.available_slots,
        bookable=(t.status == "Open" and t.available_slots > 0),
    )


@api_bp.post("/bookings")
@jwt_required("user")
def create_booking():
    data = request.get_json(silent=True) or {}
    trek_id = data.get("trek_id")
    t = db.session.get(Trek, trek_id) if trek_id else None
    if not t:
        return jsonify(error="trek not found"), 404
    # Same rules as the web booking flow.
    if t.status != "Open":
        return jsonify(error="trek not open for booking"), 409
    if t.available_slots <= 0:
        return jsonify(error="trek fully booked"), 409
    dup = Booking.query.filter_by(
        user_id=g.user_id, trek_id=t.id, status="Booked").first()
    if dup:
        return jsonify(error="already booked", booking_id=dup.id), 409

    booking = Booking(user_id=g.user_id, trek_id=t.id, status="Booked")
    t.available_slots -= 1
    db.session.add(booking)
    db.session.commit()
    send_booking_notification("booked", booking.id, f"{t.name}")
    return jsonify(booking_id=booking.id, trek=t.name,
                   available_slots=t.available_slots), 201


@api_bp.get("/bookings")
@jwt_required("user")
def my_bookings():
    rows = (Booking.query.filter_by(user_id=g.user_id)
            .order_by(Booking.booking_date.desc()).all())
    return jsonify(bookings=[
        {"id": b.id, "trek": b.trek.name, "status": b.status,
         "booked_at": b.booking_date.isoformat() if b.booking_date else None}
        for b in rows
    ])


@api_bp.post("/bookings/<int:booking_id>/cancel")
@jwt_required("user")
def cancel_booking(booking_id: int):
    b = db.session.get(Booking, booking_id)
    if not b or b.user_id != g.user_id:
        return jsonify(error="booking not found"), 404
    if b.status != "Booked":
        return jsonify(error=f"cannot cancel a {b.status} booking"), 409
    b.status = "Cancelled"
    b.trek.available_slots += 1
    db.session.commit()
    send_booking_notification("cancelled", b.id, b.trek.name)
    return jsonify(booking_id=b.id, status="Cancelled")


def register(app):
    """Attach the /api blueprint to an existing Flask app."""
    app.register_blueprint(api_bp)
    return app
