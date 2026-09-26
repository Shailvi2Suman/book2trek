"""
TrekTrack -- Trekking Management Application
Flask + Jinja2 + SQLite (via SQLAlchemy) + Bootstrap 5

Run:
    python seed.py   # once -- creates tables + the pre-existing admin account
    python app.py    # starts the dev server on http://127.0.0.1:5000

All routes live in this one file, grouped into four sections (public/auth,
admin, staff, user) rather than split into blueprints. For a project this
size, being able to read every request handler top to bottom, in order, is
worth more than the extra modularity -- especially since you need to be able
to walk through it live in the viva.
"""
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (LoginManager, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

from models import db, User, Trek, Booking

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trektrack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    """Restrict a route to logged-in users whose role is in `roles`."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('You do not have access to that page.', 'danger')
                return redirect(url_for('index'))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def _search(query, model, q):
    """Shared search-by-name-or-ID helper used by the admin list pages."""
    if not q:
        return query
    if q.isdigit():
        return query.filter((model.name.ilike(f'%{q}%')) | (model.id == int(q)))
    return query.filter(model.name.ilike(f'%{q}%'))


# ============================== PUBLIC / AUTH ===============================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        phone = request.form.get('phone', '').strip()
        role = request.form['role']

        if role not in ('staff', 'user'):
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('That email is already registered.', 'danger')
            return redirect(url_for('register'))

        status = 'pending' if role == 'staff' else 'active'
        account = User(name=name, email=email,
                        password_hash=generate_password_hash(password),
                        role=role, phone=phone, status=status)
        db.session.add(account)
        db.session.commit()

        if role == 'staff':
            flash('Registered! Your staff account needs admin approval before you can log in.', 'info')
        else:
            flash('Registration successful -- you can log in now.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))

        if user.role == 'staff' and user.status == 'pending':
            flash('Your staff account is still awaiting admin approval.', 'warning')
            return redirect(url_for('login'))

        if user.status == 'blacklisted':
            flash('This account has been blacklisted. Contact the admin.', 'danger')
            return redirect(url_for('login'))

        login_user(user)
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        if user.role == 'staff':
            return redirect(url_for('staff_dashboard'))
        return redirect(url_for('user_dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))


# =================================== ADMIN ===================================

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    return render_template(
        'admin_dashboard.html',
        total_treks=Trek.query.count(),
        total_staff=User.query.filter_by(role='staff').count(),
        total_users=User.query.filter_by(role='user').count(),
        total_bookings=Booking.query.count(),
    )


@app.route('/admin/treks')
@role_required('admin')
def admin_treks():
    q = request.args.get('q', '').strip()
    treks = _search(Trek.query, Trek, q).order_by(Trek.id.desc()).all()
    approved_staff = User.query.filter_by(role='staff', status='active').all()
    return render_template('admin_treks.html', treks=treks, q=q, approved_staff=approved_staff)


@app.route('/admin/treks/new', methods=['GET', 'POST'])
@role_required('admin')
def admin_new_trek():
    if request.method == 'POST':
        slots = int(request.form['total_slots'])
        trek = Trek(
            name=request.form['name'].strip(),
            location=request.form['location'].strip(),
            difficulty=request.form['difficulty'],
            duration_days=int(request.form['duration_days']),
            total_slots=slots,
            available_slots=slots,
            start_date=parse_date(request.form['start_date']),
            end_date=parse_date(request.form['end_date']),
            description=request.form.get('description', '').strip(),
            status='Pending',
        )
        db.session.add(trek)
        db.session.commit()
        flash('Trek created.', 'success')
        return redirect(url_for('admin_treks'))
    return render_template('admin_trek_form.html', trek=None)


@app.route('/admin/treks/<int:trek_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if request.method == 'POST':
        booked_count = trek.total_slots - trek.available_slots
        new_total = int(request.form['total_slots'])

        trek.name = request.form['name'].strip()
        trek.location = request.form['location'].strip()
        trek.difficulty = request.form['difficulty']
        trek.duration_days = int(request.form['duration_days'])
        trek.total_slots = new_total
        trek.available_slots = max(0, new_total - booked_count)
        trek.start_date = parse_date(request.form['start_date'])
        trek.end_date = parse_date(request.form['end_date'])
        trek.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('Trek updated.', 'success')
        return redirect(url_for('admin_treks'))
    return render_template('admin_trek_form.html', trek=trek)


@app.route('/admin/treks/<int:trek_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    db.session.delete(trek)
    db.session.commit()
    flash('Trek deleted.', 'info')
    return redirect(url_for('admin_treks'))


@app.route('/admin/treks/<int:trek_id>/assign', methods=['POST'])
@role_required('admin')
def admin_assign_staff(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_id = request.form.get('staff_id') or None
    trek.assigned_staff_id = int(staff_id) if staff_id else None
    if trek.assigned_staff_id and trek.status == 'Pending':
        trek.status = 'Approved'
    db.session.commit()
    flash('Assignment updated.', 'success')
    return redirect(url_for('admin_treks'))


@app.route('/admin/staff')
@role_required('admin')
def admin_staff():
    q = request.args.get('q', '').strip()
    staff_list = _search(User.query.filter_by(role='staff'), User, q).all()
    return render_template('admin_staff.html', staff_list=staff_list, q=q)


@app.route('/admin/staff/<int:staff_id>/approve', methods=['POST'])
@role_required('admin')
def admin_approve_staff(staff_id):
    staff = User.query.get_or_404(staff_id)
    staff.status = 'active'
    db.session.commit()
    flash(f'{staff.name} approved.', 'success')
    return redirect(url_for('admin_staff'))


@app.route('/admin/staff/<int:staff_id>/blacklist', methods=['POST'])
@role_required('admin')
def admin_blacklist_staff(staff_id):
    staff = User.query.get_or_404(staff_id)
    staff.status = 'blacklisted'
    db.session.commit()
    flash(f'{staff.name} blacklisted.', 'warning')
    return redirect(url_for('admin_staff'))


@app.route('/admin/users')
@role_required('admin')
def admin_users():
    q = request.args.get('q', '').strip()
    users_list = _search(User.query.filter_by(role='user'), User, q).all()
    return render_template('admin_users.html', users_list=users_list, q=q)


@app.route('/admin/users/<int:user_id>/blacklist', methods=['POST'])
@role_required('admin')
def admin_blacklist_user(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'active' if user.status == 'blacklisted' else 'blacklisted'
    db.session.commit()
    flash(f'{user.name} status updated.', 'warning')
    return redirect(url_for('admin_users'))


@app.route('/admin/bookings')
@role_required('admin')
def admin_bookings():
    bookings = Booking.query.order_by(Booking.booking_date.desc()).all()
    return render_template('admin_bookings.html', bookings=bookings)


# =================================== STAFF ===================================
@app.route('/staff/profile', methods=['GET', 'POST'])
@role_required('staff')
def staff_profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('password', '').strip()

        if not name:
            flash('Name cannot be empty.', 'danger')
            return redirect(url_for('staff_profile'))

        current_user.name = name
        current_user.phone = phone

        if new_password:
            current_user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('staff_profile'))

    return render_template('staff_profile.html')

@app.route('/staff/dashboard')
@role_required('staff')
def staff_dashboard():
    treks = Trek.query.filter_by(assigned_staff_id=current_user.id).order_by(Trek.id.desc()).all()
    return render_template('staff_dashboard.html', treks=treks)


@app.route('/staff/treks/<int:trek_id>')
@role_required('staff')
def staff_trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.assigned_staff_id != current_user.id:
        flash('You are not assigned to this trek.', 'danger')
        return redirect(url_for('staff_dashboard'))
    bookings = Booking.query.filter_by(trek_id=trek.id, status='Booked').all()
    return render_template('staff_trek_detail.html', trek=trek, bookings=bookings)


@app.route('/staff/treks/<int:trek_id>/update', methods=['POST'])
@role_required('staff')
def staff_update_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.assigned_staff_id != current_user.id:
        flash('You are not assigned to this trek.', 'danger')
        return redirect(url_for('staff_dashboard'))
    trek.available_slots = max(0, min(int(request.form['available_slots']), trek.total_slots))
    if request.form['status'] in ('Open', 'Closed'):
        trek.status = request.form['status']
    db.session.commit()
    flash('Trek updated.', 'success')
    return redirect(url_for('staff_trek_detail', trek_id=trek.id))


@app.route('/staff/treks/<int:trek_id>/complete', methods=['POST'])
@role_required('staff')
def staff_complete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.assigned_staff_id != current_user.id:
        flash('You are not assigned to this trek.', 'danger')
        return redirect(url_for('staff_dashboard'))
    trek.status = 'Completed'
    for booking in Booking.query.filter_by(trek_id=trek.id, status='Booked').all():
        booking.status = 'Completed'
    db.session.commit()
    flash('Trek marked as completed.', 'success')
    return redirect(url_for('staff_trek_detail', trek_id=trek.id))


# =================================== USER ====================================

@app.route('/user/dashboard')
@role_required('user')
def user_dashboard():
    return render_template(
        'user_dashboard.html',
        available_treks=Trek.query.filter_by(status='Open').count(),
        my_bookings=Booking.query.filter_by(user_id=current_user.id, status='Booked').all(),
        recent_bookings=Booking.query.filter_by(user_id=current_user.id)
                                      .order_by(Booking.booking_date.desc()).limit(5).all(),
    )


@app.route('/user/treks')
@role_required('user')
def user_treks():
    query = Trek.query.filter(Trek.status.in_(['Open', 'Approved']))
    difficulty = request.args.get('difficulty', '')
    location = request.args.get('location', '').strip()
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if location:
        query = query.filter(Trek.location.ilike(f'%{location}%'))
    treks = query.order_by(Trek.start_date.asc()).all()
    return render_template('user_treks.html', treks=treks, difficulty=difficulty, location=location)


@app.route('/user/treks/<int:trek_id>')
@role_required('user')
def user_trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    already_booked = Booking.query.filter_by(
        user_id=current_user.id, trek_id=trek.id, status='Booked'
    ).first() is not None
    return render_template('user_trek_detail.html', trek=trek, already_booked=already_booked)


@app.route('/user/treks/<int:trek_id>/book', methods=['POST'])
@role_required('user')
def user_book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if trek.status != 'Open':
        flash('This trek is not open for booking.', 'danger')
    elif trek.available_slots <= 0:
        flash('Sorry, this trek is fully booked.', 'danger')
    elif Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id, status='Booked').first():
        flash('You already booked this trek.', 'warning')
    else:
        db.session.add(Booking(user_id=current_user.id, trek_id=trek.id, status='Booked'))
        trek.available_slots -= 1
        db.session.commit()
        flash('Trek booked! See you on the trail.', 'success')
        return redirect(url_for('user_bookings'))

    return redirect(url_for('user_trek_detail', trek_id=trek.id))


@app.route('/user/bookings')
@role_required('user')
def user_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id) \
                             .order_by(Booking.booking_date.desc()).all()
    return render_template('user_bookings.html', bookings=bookings)


@app.route('/user/bookings/<int:booking_id>/cancel', methods=['POST'])
@role_required('user')
def user_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Not authorized.', 'danger')
    elif booking.status == 'Booked':
        booking.status = 'Cancelled'
        booking.trek.available_slots += 1
        db.session.commit()
        flash('Booking cancelled.', 'info')
    return redirect(url_for('user_bookings'))


@app.route('/user/profile', methods=['GET', 'POST'])
@role_required('user')
def user_profile():
    if request.method == 'POST':
        current_user.name = request.form['name'].strip()
        current_user.phone = request.form.get('phone', '').strip()
        new_password = request.form.get('password', '').strip()
        if new_password:
            current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('user_profile'))
    return render_template('user_profile.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
