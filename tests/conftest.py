"""
Shared test fixtures: a hermetic Flask app on in-memory SQLite with the /api
blueprint and a little seed data. No server, no Redis, no keys required.
"""
import os
from datetime import date, timedelta

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-bytes-long!!")

from book2trek.api.blueprint import register  # noqa: E402
from models import Trek, User, db  # noqa: E402


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    register(app)
    with app.app_context():
        db.create_all()
        _seed()
        yield app
        db.session.remove()
        db.drop_all()


def _seed():
    user = User(name="Trekker", email="user@example.com",
                password_hash=generate_password_hash("pw"), role="user",
                status="active")
    db.session.add(user)
    today = date.today()
    treks = [
        Trek(name="Roopkund", location="Uttarakhand", difficulty="Hard",
             duration_days=6, total_slots=10, available_slots=4, status="Open",
             start_date=today + timedelta(days=20), end_date=today + timedelta(days=26),
             description="A high-altitude glacial lake trek with the mystery skeletons."),
        Trek(name="Triund", location="Dharamshala", difficulty="Easy",
             duration_days=2, total_slots=20, available_slots=0, status="Open",
             start_date=today + timedelta(days=10), end_date=today + timedelta(days=12),
             description="A short beginner-friendly ridge trek with Dhauladhar views."),
        Trek(name="Hampta Pass", location="Manali", difficulty="Moderate",
             duration_days=4, total_slots=15, available_slots=8, status="Open",
             start_date=today + timedelta(days=15), end_date=today + timedelta(days=19),
             description="A dramatic crossover trek from green valleys to desert."),
    ]
    db.session.add_all(treks)
    db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()
