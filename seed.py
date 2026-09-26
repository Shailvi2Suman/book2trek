from app import app, db
from models import User
from werkzeug.security import generate_password_hash


ADMIN_EMAIL = "admin@trektrack.com"
ADMIN_PASSWORD = "admin123"


with app.app_context():

    # Create all database tables programmatically
    db.create_all()

    # Check whether admin already exists
    existing_admin = User.query.filter_by(
        email=ADMIN_EMAIL
    ).first()

    if existing_admin:
        print("Admin already exists.")
    else:

        admin = User(
            name="System Administrator",
            email=ADMIN_EMAIL,
            password_hash=generate_password_hash(
                ADMIN_PASSWORD
            ),
            role="admin",
            status="active"
        )

        db.session.add(admin)
        db.session.commit()

        print("===================================")
        print("Admin account created successfully")
        print("Email:", ADMIN_EMAIL)
        print("Password:", ADMIN_PASSWORD)
        print("===================================")