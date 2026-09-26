# Book2Trek — Trekking Management Application

A Flask + Jinja2 + SQLite web app for managing treks, trek staff, and trekkers,
built against the MAD-I "Trekking Management App V1" brief.

## Stack (matches the mandatory frameworks list)
- **Backend:** Flask
- **DB:** SQLite, created **programmatically** via `db.create_all()` in `seed.py` / `app.py` — never touched with DB Browser or any manual tool.
- **ORM:** Flask-SQLAlchemy (SQLite underneath — still the only DB engine used)
- **Auth:** Flask-Login for session handling + Werkzeug's `generate_password_hash`/`check_password_hash` — Flask-Login is explicitly listed as a recommended extension in the brief.
- **Frontend:** Jinja2 templates, Bootstrap 5 (CDN), custom CSS
- **JavaScript:** none written for the app. The only `<script>` tag anywhere is Bootstrap's own bundled JS in `base.html`, used purely for the collapsible navbar and dismissible alerts (UI chrome). Every actual feature — auth, booking, overbooking prevention, search, role checks — runs server-side in Python/Flask. Worth being able to say this out loud if an examiner asks about the `<script>` tag.

## Setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python seed.py                  # creates trektrack.db + the admin account
python app.py                   # http://127.0.0.1:5000
```

**Default admin login:** `admin@trektrack.com` / `admin123`
(change `ADMIN_PASSWORD` at the top of `seed.py` before you demo, if you'd rather use your own)

## Project structure
```
app.py            entry point + every route, grouped: public/auth / admin / staff / user
models.py         User, Trek, Booking (SQLAlchemy models)
seed.py           one-time script: creates tables + admin account
templates/        one Jinja2 template per page
static/style.css  theme
requirements.txt
```
Every route lives in one `app.py` (no blueprints) on purpose — being able to read the
whole request-handling logic top to bottom, in order, matters more here than the
extra modularity, especially since you need to walk through it live at the viva.

## About the zip structure
Your guidelines doc's example file tree shows `Project Report.pdf` sitting *inside*
the project root folder, while the written instructions say the report is submitted
in DOCX/PDF "in their respective fields only" (i.e. a separate upload, not bundled
into the code zip). Those two hints aren't fully consistent. To be safe: this folder
already matches the example tree structurally (single root folder, `templates/` inside
it, `app.py` at the root) — when your report is ready, drop a copy of it in here too
*in addition to* uploading it to its own field. Double-check the actual submission
portal when you get there; it'll make the expected fields obvious immediately.

## Data model
- **User** — one table for all three roles (`role` = admin/staff/user). `status`
  does double duty: `pending`/`active` for staff awaiting approval, `active`/`blacklisted`
  for anyone blocked. One table = one login form, one query.
- **Trek** — created by Admin. `assigned_staff_id` is a nullable FK to `User`.
  Status lifecycle: `Pending` → `Approved` (staff assigned) → `Open`/`Closed`
  (staff toggles) → `Completed` (staff marks done).
- **Booking** — links a trekker to a Trek. Never deleted, only its `status` changes
  (`Booked`/`Cancelled`/`Completed`) — that's how booking *history* survives for both
  the trekker's own view and the admin's "all bookings" view.

Relationships: one Trek → many Bookings; one staff User → many assigned Treks;
one trekker User → many Bookings. Happy to generate an actual ER diagram image for
the report if you want one — just ask.

## Requirement → code map
Useful for the report *and* the viva — if an examiner points at a requirement, you
should be able to name the file/route on the spot, not go searching for it.

| Requirement | Where |
|---|---|
| Prevent overbooking | `user_book_trek()` in `app.py` — checks `available_slots > 0` before creating a Booking |
| Only assigned staff manages a trek | every `/staff/...` route checks `trek.assigned_staff_id != current_user.id` |
| Book only if status is Open | `user_book_trek()` checks `trek.status != 'Open'` |
| Admin approves staff | `admin_approve_staff()` flips `status` `pending` → `active`; login route blocks `pending` staff |
| Blacklist users/staff | `admin_blacklist_staff()` / `admin_blacklist_user()`; login route blocks `status == 'blacklisted'` |
| Search by name or ID | `_search()` helper in `app.py`, shared by the treks/staff/users list routes |
| Booking/trek history preserved | Bookings are never deleted, only status-changed |
| Role-based access control | `role_required()` decorator, applied to every protected route |


