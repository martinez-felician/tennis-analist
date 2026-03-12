import os
import json
import secrets
import sqlite3
from functools import wraps

import stripe
from flask import Flask, request, jsonify, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'tennis.db')

# Persist secret key across restarts so sessions survive
_key_file = os.path.join(BASE_DIR, '.secret_key')
if 'SECRET_KEY' in os.environ:
    app.secret_key = os.environ['SECRET_KEY']
elif os.path.exists(_key_file):
    app.secret_key = open(_key_file).read().strip()
else:
    _k = secrets.token_hex(32)
    open(_key_file, 'w').write(_k)
    app.secret_key = _k

# Stripe config — set these as environment variables
stripe.api_key            = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PRICE_ID           = os.environ.get('STRIPE_PRICE_ID', '')
STRIPE_WEBHOOK_SECRET     = os.environ.get('STRIPE_WEBHOOK_SECRET', '')


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT    UNIQUE NOT NULL,
            email               TEXT    UNIQUE NOT NULL,
            password_hash       TEXT    NOT NULL,
            is_premium          INTEGER NOT NULL DEFAULT 0,
            stripe_customer_id  TEXT,
            subscription_status TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS matches (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            config     TEXT    NOT NULL,
            stats      TEXT    NOT NULL,
            result     TEXT    NOT NULL,
            played_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    # Migrate existing DB: add new columns if they don't exist yet
    for col, definition in [
        ('is_premium',          'INTEGER NOT NULL DEFAULT 0'),
        ('stripe_customer_id',  'TEXT'),
        ('subscription_status', 'TEXT'),
        ('first_name',          'TEXT DEFAULT ""'),
        ('last_name',           'TEXT DEFAULT ""'),
    ]:
        try:
            conn.execute(f'ALTER TABLE users ADD COLUMN {col} {definition}')
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Static files ──────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/home')
def home_page():
    return send_from_directory(BASE_DIR, 'home.html')

@app.route('/login')
def login_page():
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/profile')
def profile_page():
    return send_from_directory(BASE_DIR, 'profile.html')

@app.route('/style.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'style.css')

@app.route('/script.js')
def serve_js():
    return send_from_directory(BASE_DIR, 'script.js')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(BASE_DIR, 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(BASE_DIR, 'sw.js')

@app.route('/icon.svg')
def serve_icon():
    return send_from_directory(BASE_DIR, 'icon.svg')

@app.route('/logo.svg')
def serve_logo():
    return send_from_directory(BASE_DIR, 'logo.svg')


# ── Auth API ──────────────────────────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("10 per hour")
def register():
    data     = request.get_json(silent=True) or {}
    if not isinstance(data, dict): data = {}
    username = (data.get('username') or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(username) < 2:
        return jsonify({'error': 'Username must be at least 2 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()
        return jsonify({'message': 'Account created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already in use'}), 409


@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("20 per hour")
def login():
    data     = request.get_json(silent=True) or {}
    if not isinstance(data, dict): data = {}
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password') or ''

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']
    return jsonify({'username': user['username']})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})


@app.route('/api/auth/me')
def me():
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 401
    conn = get_db()
    user = conn.execute(
        'SELECT is_premium, subscription_status, first_name, last_name FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()
    return jsonify({
        'authenticated':       True,
        'user_id':             session['user_id'],
        'username':            session['username'],
        'first_name':          user['first_name'] if user else '',
        'last_name':           user['last_name']  if user else '',
        'is_premium':          bool(user['is_premium']) if user else False,
        'subscription_status': user['subscription_status'] if user else None,
    })


@app.route('/api/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    data       = request.get_json(silent=True) or {}
    if not isinstance(data, dict): data = {}
    username   = (data.get('username')   or '').strip()
    first_name = (data.get('first_name') or '').strip()
    last_name  = (data.get('last_name')  or '').strip()

    if username and len(username) < 2:
        return jsonify({'error': 'Display name must be at least 2 characters'}), 400

    conn = get_db()
    current = conn.execute('SELECT username FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    new_username = username if username else current['username']

    if username and username != current['username']:
        exists = conn.execute('SELECT id FROM users WHERE username = ? AND id != ?',
                              (username, session['user_id'])).fetchone()
        if exists:
            conn.close()
            return jsonify({'error': 'That display name is already taken'}), 409

    conn.execute(
        'UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE id = ?',
        (new_username, first_name, last_name, session['user_id'])
    )
    conn.commit()
    conn.close()
    session['username'] = new_username
    return jsonify({'username': new_username, 'first_name': first_name, 'last_name': last_name})


@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    data             = request.get_json(silent=True) or {}
    if not isinstance(data, dict): data = {}
    current_password =  data.get('current_password') or ''
    new_password     =  data.get('new_password')     or ''

    if not current_password or not new_password:
        return jsonify({'error': 'Both fields are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    conn = get_db()
    user = conn.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if not user or not check_password_hash(user['password_hash'], current_password):
        conn.close()
        return jsonify({'error': 'Current password is incorrect'}), 401

    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (generate_password_hash(new_password), session['user_id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Password updated successfully'})


@app.route('/api/auth/account', methods=['DELETE'])
@login_required
def delete_account():
    user_id = session['user_id']
    conn = get_db()
    conn.execute('DELETE FROM matches WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({'message': 'Account deleted'}), 200


# ── Matches API ───────────────────────────────────────────────────────────────

@app.route('/api/matches', methods=['GET'])
@login_required
def get_matches():
    conn = get_db()
    rows = conn.execute(
        'SELECT id, config, stats, result, played_at FROM matches '
        'WHERE user_id = ? ORDER BY id DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/matches', methods=['POST'])
@login_required
def save_match():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict): data = {}
    conn = get_db()
    conn.execute(
        'INSERT INTO matches (user_id, config, stats, result) VALUES (?, ?, ?, ?)',
        (
            session['user_id'],
            json.dumps(data.get('config', {})),
            json.dumps(data.get('stats',  {})),
            json.dumps(data.get('result', {})),
        )
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Match saved'}), 201


# ── Billing API ───────────────────────────────────────────────────────────────

@app.route('/api/billing/checkout', methods=['POST'])
@login_required
def create_checkout():
    if not stripe.api_key or not STRIPE_PRICE_ID:
        return jsonify({'error': 'Billing not configured'}), 503

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    # Get or create Stripe customer
    customer_id = user['stripe_customer_id']
    if not customer_id:
        customer = stripe.Customer.create(
            email=user['email'],
            name=user['username'],
            metadata={'user_id': session['user_id']},
        )
        customer_id = customer.id
        conn = get_db()
        conn.execute(
            'UPDATE users SET stripe_customer_id = ? WHERE id = ?',
            (customer_id, session['user_id'])
        )
        conn.commit()
        conn.close()

    base_url = request.host_url.rstrip('/')
    checkout = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
        mode='subscription',
        success_url=base_url + '/profile?upgraded=1',
        cancel_url=base_url + '/profile',
    )
    return jsonify({'url': checkout.url})


@app.route('/api/billing/portal', methods=['POST'])
@login_required
def billing_portal():
    if not stripe.api_key:
        return jsonify({'error': 'Billing not configured'}), 503

    conn = get_db()
    user = conn.execute(
        'SELECT stripe_customer_id FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()

    if not user or not user['stripe_customer_id']:
        return jsonify({'error': 'No billing account found'}), 404

    base_url = request.host_url.rstrip('/')
    portal = stripe.billing_portal.Session.create(
        customer=user['stripe_customer_id'],
        return_url=base_url + '/profile',
    )
    return jsonify({'url': portal.url})


@app.route('/api/billing/webhook', methods=['POST'])
def stripe_webhook():
    payload    = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return '', 400

    obj = event['data']['object']
    if event['type'] in ('customer.subscription.created', 'customer.subscription.updated'):
        _update_subscription(obj['customer'], obj['status'])
    elif event['type'] == 'customer.subscription.deleted':
        _update_subscription(obj['customer'], 'canceled')

    return '', 200


def _update_subscription(customer_id, status):
    is_premium = 1 if status == 'active' else 0
    conn = get_db()
    conn.execute(
        'UPDATE users SET is_premium = ?, subscription_status = ? WHERE stripe_customer_id = ?',
        (is_premium, status, customer_id)
    )
    conn.commit()
    conn.close()


# ── Run ───────────────────────────────────────────────────────────────────────

init_db()  # runs on every startup (local dev & PythonAnywhere WSGI)

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, port=5000)
