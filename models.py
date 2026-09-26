from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # admin | staff | user
    role = db.Column(db.String(20), nullable=False)

    phone = db.Column(db.String(20))

    # staff: pending | active | blacklisted
    # user: active | blacklisted
    # admin: active
    status = db.Column(db.String(20), default="active", nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    bookings = db.relationship(
        "Booking",
        backref="user",
        foreign_keys="Booking.user_id",
        cascade="all, delete-orphan"
    )

    assigned_treks = db.relationship(
        "Trek",
        backref="staff",
        foreign_keys="Trek.assigned_staff_id"
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Trek(db.Model):
    __tablename__ = "trek"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(150),
        nullable=False
    )

    location = db.Column(
        db.String(150),
        nullable=False
    )

    difficulty = db.Column(
        db.String(20),
        nullable=False
    )

    duration_days = db.Column(
        db.Integer,
        nullable=False
    )

    total_slots = db.Column(
        db.Integer,
        nullable=False
    )

    available_slots = db.Column(
        db.Integer,
        nullable=False
    )

    assigned_staff_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    # Pending | Approved | Open | Closed | Completed
    status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    start_date = db.Column(
        db.Date,
        nullable=False
    )

    end_date = db.Column(
        db.Date,
        nullable=False
    )

    description = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    bookings = db.relationship(
        "Booking",
        backref="trek",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Trek {self.name}>"


class Booking(db.Model):
    __tablename__ = "booking"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    trek_id = db.Column(
        db.Integer,
        db.ForeignKey("trek.id"),
        nullable=False
    )

    booking_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Booked | Cancelled | Completed
    status = db.Column(
        db.String(20),
        default="Booked",
        nullable=False
    )

    def __repr__(self):
        return f"<Booking user={self.user_id} trek={self.trek_id}>"