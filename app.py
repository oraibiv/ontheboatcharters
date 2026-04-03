"""
On The Boat Charters — Booking & Management System
Flask app with SQLite backend, Stripe payments, admin dashboard.
"""

import os
import sqlite3
import json
import secrets
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from mailer import (
    send_booking_confirmation, send_cancellation_notice,
    send_trip_reminder, send_captain_digest, GMAIL_ADDRESS
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Railway persistent volume: set DATABASE env var to /data/ontheboat.db
# and attach a volume mounted at /data in Railway dashboard
_default_db = '/data/ontheboat.db' if os.path.isdir('/data') else 'ontheboat.db'
app.config['DATABASE'] = os.environ.get('DATABASE', _default_db)
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY', '')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY', '')

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    # Seed admin user if none exists
    row = db.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not row:
        db.execute(
            "INSERT INTO users (email, name, phone, password_hash, role) VALUES (?,?,?,?,?)",
            ('admin@ontheboatcharters.com', 'Captain',  '', generate_password_hash('charter2025'), 'admin')
        )
    # Seed trip types from current site
    if db.execute("SELECT COUNT(*) FROM trip_types").fetchone()[0] == 0:
        trips = [
            ('Offshore Fishing Charter', 'Full day offshore excursion targeting tuna, shark, codfish, mahi mahi, or marlin.', 800.00, 480, 6),
            ('Sunset Cruise', 'Relaxing evening cruise around Martha\'s Vineyard with stunning sunset views.', 400.00, 120, 10),
            ('Tuna Charter', 'Dedicated tuna fishing trip for serious anglers.', 900.00, 480, 6),
            ('Cuttyhunk Shuttle', 'Scenic boat shuttle from Martha\'s Vineyard to Cuttyhunk Island.', 150.00, 90, 12),
            ('Falmouth Shuttle', 'Convenient boat shuttle between Martha\'s Vineyard and Falmouth.', 100.00, 60, 12),
            ('Near Shore Fishing', 'Half-day inshore fishing trip departing from Oak Bluffs.', 500.00, 240, 6),
        ]
        db.executemany(
            "INSERT INTO trip_types (name, description, base_price, duration_minutes, max_passengers) VALUES (?,?,?,?,?)",
            trips
        )
    db.commit()
    db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',  -- 'admin' or 'customer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trip_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    base_price REAL NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 120,
    max_passengers INTEGER NOT NULL DEFAULT 6,
    active INTEGER DEFAULT 1,
    image_url TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS available_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_type_id INTEGER NOT NULL,
    slot_date DATE NOT NULL,
    slot_time TEXT NOT NULL,          -- e.g. '07:00'
    custom_price REAL,                -- NULL = use base_price
    spots_remaining INTEGER,          -- NULL = use trip_type max
    status TEXT DEFAULT 'open',       -- 'open', 'full', 'cancelled'
    notes TEXT DEFAULT '',
    FOREIGN KEY (trip_type_id) REFERENCES trip_types(id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    num_passengers INTEGER NOT NULL DEFAULT 1,
    total_price REAL NOT NULL,
    status TEXT DEFAULT 'pending',    -- 'pending', 'confirmed', 'cancelled', 'refunded'
    stripe_payment_id TEXT DEFAULT '',
    booking_ref TEXT UNIQUE NOT NULL,
    special_requests TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (slot_id) REFERENCES available_slots(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    invoice_number TEXT UNIQUE NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'unpaid',     -- 'unpaid', 'paid', 'refunded', 'void'
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);

CREATE INDEX IF NOT EXISTS idx_slots_date ON available_slots(slot_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
""";


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def current_user():
    if 'user_id' in session:
        return get_db().execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    return None


@app.context_processor
def inject_user():
    return dict(current_user=current_user(), now=datetime.now())


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    db = get_db()
    trip_types = db.execute("SELECT * FROM trip_types WHERE active=1 ORDER BY base_price").fetchall()
    # Get next available slot per trip type
    upcoming = {}
    for t in trip_types:
        slot = db.execute("""
            SELECT slot_date, slot_time FROM available_slots
            WHERE trip_type_id=? AND status='open' AND slot_date >= date('now')
            ORDER BY slot_date, slot_time LIMIT 1
        """, (t['id'],)).fetchone()
        upcoming[t['id']] = slot
    return render_template('index.html', trip_types=trip_types, upcoming=upcoming)


@app.route('/book/<int:trip_type_id>')
def book_trip(trip_type_id):
    db = get_db()
    trip = db.execute("SELECT * FROM trip_types WHERE id=? AND active=1", (trip_type_id,)).fetchone()
    if not trip:
        abort(404)
    slots = db.execute("""
        SELECT * FROM available_slots
        WHERE trip_type_id=? AND status='open' AND slot_date >= date('now')
        ORDER BY slot_date, slot_time
    """, (trip_type_id,)).fetchall()
    return render_template('book.html', trip=trip, slots=slots)


@app.route('/book/<int:trip_type_id>/confirm', methods=['POST'])
@login_required
def confirm_booking(trip_type_id):
    db = get_db()
    slot_id = request.form.get('slot_id', type=int)
    num_passengers = request.form.get('num_passengers', 1, type=int)
    special_requests = request.form.get('special_requests', '').strip()

    slot = db.execute("SELECT * FROM available_slots WHERE id=? AND status='open'", (slot_id,)).fetchone()
    trip = db.execute("SELECT * FROM trip_types WHERE id=?", (trip_type_id,)).fetchone()
    if not slot or not trip:
        flash('That slot is no longer available.', 'error')
        return redirect(url_for('book_trip', trip_type_id=trip_type_id))

    remaining = slot['spots_remaining'] if slot['spots_remaining'] is not None else trip['max_passengers']
    if num_passengers > remaining:
        flash(f'Only {remaining} spots left on this trip.', 'error')
        return redirect(url_for('book_trip', trip_type_id=trip_type_id))

    price_per = slot['custom_price'] if slot['custom_price'] else trip['base_price']
    total = price_per * num_passengers
    booking_ref = f"OTB-{secrets.token_hex(4).upper()}"
    invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    # Create booking
    cur = db.execute("""
        INSERT INTO bookings (user_id, slot_id, num_passengers, total_price, status, booking_ref, special_requests)
        VALUES (?,?,?,?,?,?,?)
    """, (session['user_id'], slot_id, num_passengers, total, 'confirmed', booking_ref, special_requests))
    booking_id = cur.lastrowid

    # Create invoice
    db.execute("""
        INSERT INTO invoices (booking_id, invoice_number, amount, status, paid_at)
        VALUES (?,?,?,?,?)
    """, (booking_id, invoice_number, total, 'paid', datetime.now().isoformat()))

    # Update spots remaining
    new_remaining = remaining - num_passengers
    if new_remaining <= 0:
        db.execute("UPDATE available_slots SET spots_remaining=0, status='full' WHERE id=?", (slot_id,))
    else:
        db.execute("UPDATE available_slots SET spots_remaining=? WHERE id=?", (new_remaining, slot_id))

    db.commit()

    # Send confirmation email
    user = db.execute("SELECT name, email FROM users WHERE id=?", (session['user_id'],)).fetchone()
    send_booking_confirmation(
        customer_email=user['email'],
        customer_name=user['name'],
        booking_ref=booking_ref,
        trip_name=trip['name'],
        slot_date=slot['slot_date'],
        slot_time=slot['slot_time'],
        num_passengers=num_passengers,
        total_price=total,
        special_requests=special_requests,
    )

    flash(f'Booking confirmed! Reference: {booking_ref}', 'success')
    return redirect(url_for('my_bookings'))


@app.route('/my-bookings')
@login_required
def my_bookings():
    db = get_db()
    bookings = db.execute("""
        SELECT b.*, s.slot_date, s.slot_time, t.name as trip_name, t.duration_minutes,
               i.invoice_number, i.status as invoice_status
        FROM bookings b
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
        LEFT JOIN invoices i ON i.booking_id = b.id
        WHERE b.user_id = ?
        ORDER BY s.slot_date DESC
    """, (session['user_id'],)).fetchall()
    return render_template('my_bookings.html', bookings=bookings)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['user_name'] = user['name']
            next_url = request.args.get('next', url_for('admin_dashboard') if user['role'] == 'admin' else url_for('index'))
            return redirect(next_url)
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        db = get_db()
        email = request.form['email'].strip().lower()
        name = request.form['name'].strip()
        phone = request.form.get('phone', '').strip()
        password = request.form['password']

        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash('An account with that email already exists.', 'error')
            return render_template('signup.html')

        db.execute(
            "INSERT INTO users (email, name, phone, password_hash, role) VALUES (?,?,?,?,?)",
            (email, name, phone, generate_password_hash(password), 'customer')
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['user_name'] = user['name']
        flash('Welcome aboard!', 'success')
        return redirect(url_for('index'))
    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    today = date.today().isoformat()

    # Today's schedule
    todays_bookings = db.execute("""
        SELECT b.*, s.slot_date, s.slot_time, t.name as trip_name,
               u.name as customer_name, u.phone as customer_phone, u.email as customer_email
        FROM bookings b
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
        JOIN users u ON b.user_id = u.id
        WHERE s.slot_date = ? AND b.status IN ('confirmed', 'pending')
        ORDER BY s.slot_time
    """, (today,)).fetchall()

    # Upcoming slots (next 14 days)
    upcoming_slots = db.execute("""
        SELECT s.*, t.name as trip_name, t.base_price,
               COUNT(b.id) as booking_count,
               SUM(CASE WHEN b.status IN ('confirmed','pending') THEN b.num_passengers ELSE 0 END) as passengers_booked
        FROM available_slots s
        JOIN trip_types t ON s.trip_type_id = t.id
        LEFT JOIN bookings b ON b.slot_id = s.id
        WHERE s.slot_date >= ? AND s.slot_date <= date(?, '+14 days')
        GROUP BY s.id
        ORDER BY s.slot_date, s.slot_time
    """, (today, today)).fetchall()

    # Revenue stats
    revenue_today = db.execute("""
        SELECT COALESCE(SUM(i.amount), 0) as total FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN available_slots s ON b.slot_id = s.id
        WHERE i.status='paid' AND s.slot_date = ?
    """, (today,)).fetchone()['total']

    revenue_week = db.execute("""
        SELECT COALESCE(SUM(i.amount), 0) as total FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN available_slots s ON b.slot_id = s.id
        WHERE i.status='paid' AND s.slot_date >= date(?, '-7 days') AND s.slot_date <= ?
    """, (today, today)).fetchone()['total']

    revenue_month = db.execute("""
        SELECT COALESCE(SUM(i.amount), 0) as total FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN available_slots s ON b.slot_id = s.id
        WHERE i.status='paid' AND s.slot_date >= date(?, 'start of month') AND s.slot_date <= ?
    """, (today, today)).fetchone()['total']

    revenue_season = db.execute("""
        SELECT COALESCE(SUM(i.amount), 0) as total FROM invoices i
        WHERE i.status='paid'
    """).fetchone()['total']

    total_customers = db.execute("SELECT COUNT(*) as c FROM users WHERE role='customer'").fetchone()['c']

    # Revenue by trip type
    revenue_by_trip = db.execute("""
        SELECT t.name, COALESCE(SUM(i.amount), 0) as total, COUNT(b.id) as trips
        FROM trip_types t
        LEFT JOIN available_slots s ON s.trip_type_id = t.id
        LEFT JOIN bookings b ON b.slot_id = s.id AND b.status IN ('confirmed','pending')
        LEFT JOIN invoices i ON i.booking_id = b.id AND i.status = 'paid'
        GROUP BY t.id
        ORDER BY total DESC
    """).fetchall()

    return render_template('admin/dashboard.html',
        todays_bookings=todays_bookings,
        upcoming_slots=upcoming_slots,
        revenue_today=revenue_today,
        revenue_week=revenue_week,
        revenue_month=revenue_month,
        revenue_season=revenue_season,
        total_customers=total_customers,
        revenue_by_trip=revenue_by_trip,
    )


@app.route('/admin/slots', methods=['GET', 'POST'])
@admin_required
def admin_slots():
    db = get_db()
    if request.method == 'POST':
        trip_type_id = request.form['trip_type_id']
        slot_date = request.form['slot_date']
        slot_time = request.form['slot_time']
        custom_price = request.form.get('custom_price', '').strip()
        custom_price = float(custom_price) if custom_price else None
        spots = request.form.get('spots_remaining', '').strip()
        spots = int(spots) if spots else None
        notes = request.form.get('notes', '').strip()

        # Support bulk date creation
        end_date = request.form.get('end_date', '').strip()
        days_of_week = request.form.getlist('days_of_week')  # e.g. ['1','3','5'] for Mon/Wed/Fri

        if end_date and days_of_week:
            start = datetime.strptime(slot_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            dow_ints = [int(d) for d in days_of_week]
            count = 0
            current = start
            while current <= end:
                if current.isoweekday() in dow_ints:
                    db.execute("""
                        INSERT INTO available_slots (trip_type_id, slot_date, slot_time, custom_price, spots_remaining, notes)
                        VALUES (?,?,?,?,?,?)
                    """, (trip_type_id, current.isoformat(), slot_time, custom_price, spots, notes))
                    count += 1
                current += timedelta(days=1)
            db.commit()
            flash(f'Created {count} slots.', 'success')
        else:
            db.execute("""
                INSERT INTO available_slots (trip_type_id, slot_date, slot_time, custom_price, spots_remaining, notes)
                VALUES (?,?,?,?,?,?)
            """, (trip_type_id, slot_date, slot_time, custom_price, spots, notes))
            db.commit()
            flash('Slot created.', 'success')

        return redirect(url_for('admin_slots'))

    trip_types = db.execute("SELECT * FROM trip_types WHERE active=1").fetchall()
    slots = db.execute("""
        SELECT s.*, t.name as trip_name, t.base_price, t.max_passengers,
               COUNT(b.id) as booking_count
        FROM available_slots s
        JOIN trip_types t ON s.trip_type_id = t.id
        LEFT JOIN bookings b ON b.slot_id = s.id AND b.status IN ('confirmed','pending')
        WHERE s.slot_date >= date('now')
        GROUP BY s.id
        ORDER BY s.slot_date, s.slot_time
    """).fetchall()
    return render_template('admin/slots.html', trip_types=trip_types, slots=slots)


@app.route('/admin/slots/<int:slot_id>/cancel', methods=['POST'])
@admin_required
def cancel_slot(slot_id):
    db = get_db()
    db.execute("UPDATE available_slots SET status='cancelled' WHERE id=?", (slot_id,))
    db.execute("""
        UPDATE bookings SET status='cancelled', updated_at=CURRENT_TIMESTAMP
        WHERE slot_id=? AND status IN ('confirmed','pending')
    """, (slot_id,))
    db.commit()
    flash('Slot cancelled.', 'success')
    return redirect(url_for('admin_slots'))


@app.route('/admin/customers')
@admin_required
def admin_customers():
    db = get_db()
    customers = db.execute("""
        SELECT u.*, COUNT(b.id) as total_bookings,
               COALESCE(SUM(CASE WHEN b.status='confirmed' THEN b.total_price ELSE 0 END), 0) as total_spent
        FROM users u
        LEFT JOIN bookings b ON b.user_id = u.id
        WHERE u.role = 'customer'
        GROUP BY u.id
        ORDER BY total_spent DESC
    """).fetchall()
    return render_template('admin/customers.html', customers=customers)


@app.route('/admin/customers/<int:user_id>')
@admin_required
def admin_customer_detail(user_id):
    db = get_db()
    customer = db.execute("SELECT * FROM users WHERE id=? AND role='customer'", (user_id,)).fetchone()
    if not customer:
        abort(404)
    bookings = db.execute("""
        SELECT b.*, s.slot_date, s.slot_time, t.name as trip_name,
               i.invoice_number, i.status as invoice_status
        FROM bookings b
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
        LEFT JOIN invoices i ON i.booking_id = b.id
        WHERE b.user_id = ?
        ORDER BY s.slot_date DESC
    """, (user_id,)).fetchall()
    return render_template('admin/customer_detail.html', customer=customer, bookings=bookings)


@app.route('/admin/invoices')
@admin_required
def admin_invoices():
    db = get_db()
    status_filter = request.args.get('status', '')
    query = """
        SELECT i.*, b.booking_ref, b.num_passengers, u.name as customer_name, u.email as customer_email,
               s.slot_date, s.slot_time, t.name as trip_name
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN users u ON b.user_id = u.id
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
    """
    params = []
    if status_filter:
        query += " WHERE i.status = ?"
        params.append(status_filter)
    query += " ORDER BY i.issued_at DESC"
    invoices = db.execute(query, params).fetchall()
    return render_template('admin/invoices.html', invoices=invoices, status_filter=status_filter)


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    db = get_db()
    bookings = db.execute("""
        SELECT b.*, s.slot_date, s.slot_time, t.name as trip_name,
               u.name as customer_name, u.email as customer_email, u.phone as customer_phone,
               i.invoice_number, i.status as invoice_status
        FROM bookings b
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
        JOIN users u ON b.user_id = u.id
        LEFT JOIN invoices i ON i.booking_id = b.id
        ORDER BY s.slot_date DESC, s.slot_time
    """).fetchall()
    return render_template('admin/bookings.html', bookings=bookings)


@app.route('/admin/bookings/<int:booking_id>/cancel', methods=['POST'])
@admin_required
def cancel_booking(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if booking:
        db.execute("UPDATE bookings SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?", (booking_id,))
        db.execute("UPDATE invoices SET status='void' WHERE booking_id=?", (booking_id,))
        # Restore spots
        slot = db.execute("SELECT * FROM available_slots WHERE id=?", (booking['slot_id'],)).fetchone()
        if slot:
            new_spots = (slot['spots_remaining'] or 0) + booking['num_passengers']
            db.execute("UPDATE available_slots SET spots_remaining=?, status='open' WHERE id=?", (new_spots, slot['id']))
        db.commit()

        # Send cancellation email
        cust = db.execute("SELECT name, email FROM users WHERE id=?", (booking['user_id'],)).fetchone()
        slot_info = db.execute("""
            SELECT s.slot_date, s.slot_time, t.name as trip_name
            FROM available_slots s JOIN trip_types t ON s.trip_type_id = t.id
            WHERE s.id=?
        """, (booking['slot_id'],)).fetchone()
        if cust and slot_info:
            send_cancellation_notice(
                customer_email=cust['email'],
                customer_name=cust['name'],
                booking_ref=booking['booking_ref'],
                trip_name=slot_info['trip_name'],
                slot_date=slot_info['slot_date'],
                slot_time=slot_info['slot_time'],
            )

        flash('Booking cancelled.', 'success')
    return redirect(url_for('admin_bookings'))


@app.route('/admin/trips', methods=['GET', 'POST'])
@admin_required
def admin_trips():
    db = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        base_price = float(request.form['base_price'])
        duration = int(request.form['duration_minutes'])
        max_pass = int(request.form['max_passengers'])

        trip_id = request.form.get('trip_id', '').strip()
        if trip_id:
            db.execute("""
                UPDATE trip_types SET name=?, description=?, base_price=?, duration_minutes=?, max_passengers=?
                WHERE id=?
            """, (name, description, base_price, duration, max_pass, int(trip_id)))
            flash('Trip type updated.', 'success')
        else:
            db.execute("""
                INSERT INTO trip_types (name, description, base_price, duration_minutes, max_passengers)
                VALUES (?,?,?,?,?)
            """, (name, description, base_price, duration, max_pass))
            flash('Trip type created.', 'success')
        db.commit()
        return redirect(url_for('admin_trips'))

    trip_types = db.execute("SELECT * FROM trip_types ORDER BY name").fetchall()
    return render_template('admin/trips.html', trip_types=trip_types)


@app.route('/admin/email', methods=['GET', 'POST'])
@admin_required
def admin_email_settings():
    if request.method == 'POST':
        test_email = request.form.get('test_email', '').strip()
        if test_email:
            from mailer import send_booking_confirmation
            ok = send_booking_confirmation(
                customer_email=test_email,
                customer_name='Test Customer',
                booking_ref='OTB-TEST1234',
                trip_name='Sunset Cruise (Test)',
                slot_date='2025-07-15',
                slot_time='17:00',
                num_passengers=2,
                total_price=800,
                special_requests='This is a test email',
            )
            if ok:
                flash(f'Test email sent to {test_email}!', 'success')
            else:
                flash('Failed to send — check your Gmail credentials.', 'error')
        return redirect(url_for('admin_email_settings'))

    return render_template('admin/email_settings.html',
        email_configured=bool(GMAIL_ADDRESS),
        gmail_address=GMAIL_ADDRESS,
    )


# ---------------------------------------------------------------------------
# API endpoints for AJAX
# ---------------------------------------------------------------------------

@app.route('/api/revenue-chart')
@admin_required
def api_revenue_chart():
    db = get_db()
    days = int(request.args.get('days', 30))
    today = date.today()
    data = []
    for i in range(days, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        rev = db.execute("""
            SELECT COALESCE(SUM(i.amount), 0) as total FROM invoices i
            JOIN bookings b ON i.booking_id = b.id
            JOIN available_slots s ON b.slot_id = s.id
            WHERE i.status='paid' AND s.slot_date = ?
        """, (d,)).fetchone()['total']
        data.append({'date': d, 'revenue': rev})
    return jsonify(data)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print("\n  On The Boat Charters — Management System")
    print("  =========================================")
    print(f"  Public site:  http://localhost:{port}")
    print("  Admin login:  /login")
    print("    Email:      admin@ontheboatcharters.com")
    print("    Password:   charter2025\n")
    app.run(debug=debug, port=port, host='0.0.0.0')

