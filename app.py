import os
import csv
import io
import json
import logging
import secrets
import smtplib
import sqlite3
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from functools import wraps

import stripe
from flask import Flask, request, jsonify, session, send_from_directory, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger('tennis_analyst')

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

# SMTP config — set these as environment variables to enable password reset emails
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')


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
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            token      TEXT    UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def send_reset_email(to_address, token):
    if not SMTP_HOST or not SMTP_USER:
        logger.warning('SMTP not configured — skipping reset email for %s', to_address)
        return False
    reset_url = f'{APP_BASE_URL}/login?reset={token}'
    body = (
        f'Click the link below to reset your Tennis Analyst password (expires in 1 hour):\n\n'
        f'{reset_url}\n\n'
        f'If you did not request this, ignore this email.'
    )
    msg = MIMEText(body)
    msg['Subject'] = 'Reset your Tennis Analyst password'
    msg['From']    = SMTP_FROM
    msg['To']      = to_address
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_address], msg.as_string())
        return True
    except Exception as e:
        logger.error('Failed to send reset email to %s: %s', to_address, e)
        return False


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
    if len(password) < 8 or not any(c.isdigit() for c in password):
        return jsonify({'error': 'Password must be at least 8 characters and contain at least one number'}), 400

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()
        logger.info('New user registered — username: %s, email: %s', username, email)
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
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        logger.warning('Failed login attempt — email: %s, IP: %s', email, ip)
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']
    return jsonify({'username': user['username']})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})


@app.route('/api/auth/forgot-password', methods=['POST'])
@limiter.limit("5 per hour")
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    conn = get_db()
    user = conn.execute('SELECT id, email FROM users WHERE email = ?', (email,)).fetchone()
    if user:
        token      = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        conn.execute(
            'INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)',
            (user['id'], token, expires_at.isoformat())
        )
        conn.commit()
        send_reset_email(user['email'], token)
    conn.close()
    return jsonify({'message': 'If that email exists, a reset link has been sent.'}), 200


@app.route('/api/auth/reset-password', methods=['POST'])
@limiter.limit("10 per hour")
def reset_password():
    data     = request.get_json(silent=True) or {}
    token    = (data.get('token')    or '').strip()
    password =  data.get('password') or ''
    if not token or not password:
        return jsonify({'error': 'Token and new password are required'}), 400
    if len(password) < 8 or not any(c.isdigit() for c in password):
        return jsonify({'error': 'Password must be at least 8 characters and contain a number'}), 400
    conn = get_db()
    row = conn.execute(
        'SELECT id, user_id, expires_at, used FROM reset_tokens WHERE token = ?', (token,)
    ).fetchone()
    if not row or row['used']:
        conn.close()
        return jsonify({'error': 'Invalid or already-used reset link'}), 400
    if datetime.utcnow() > datetime.fromisoformat(row['expires_at']):
        conn.close()
        return jsonify({'error': 'Reset link has expired'}), 400
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                 (generate_password_hash(password), row['user_id']))
    conn.execute('UPDATE reset_tokens SET used = 1 WHERE id = ?', (row['id'],))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Password reset successfully'})


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
    if len(new_password) < 8 or not any(c.isdigit() for c in new_password):
        return jsonify({'error': 'New password must be at least 8 characters and contain at least one number'}), 400

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


@app.route('/api/matches/export', methods=['GET'])
@login_required
def export_matches_csv():
    WIN_KEYS  = ['ace','fh-win','bh-win','vol','oh','drop','opp-err']
    LOSS_KEYS = ['df','fh-ue','bh-ue','fh-fe','bh-fe','opp-win','miss-return','vol-err','oh-err','drop-err']
    conn = get_db()
    rows = conn.execute(
        'SELECT id, config, stats, result, played_at FROM matches '
        'WHERE user_id = ? ORDER BY id ASC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['match_id','played_at','player_name','opponent_name',
                     'sets_won','sets_lost','result','total_points',
                     'points_won','points_lost','win_rate_pct'])
    for r in rows:
        try: config = json.loads(r['config'])
        except Exception: config = {}
        try: stats  = json.loads(r['stats'])
        except Exception: stats  = {}
        try: result = json.loads(r['result'])
        except Exception: result = {}
        pts_won  = sum(stats.get(k, 0) for k in WIN_KEYS)
        pts_lost = sum(stats.get(k, 0) for k in LOSS_KEYS)
        total    = pts_won + pts_lost
        win_rate = round(pts_won / total * 100, 1) if total else 0
        writer.writerow([
            r['id'], r['played_at'],
            config.get('playerName',''), config.get('opponentName',''),
            result.get('player1Sets',''), result.get('player2Sets',''),
            'Won' if result.get('won') else 'Lost',
            total, pts_won, pts_lost, win_rate,
        ])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=match_history.csv'}
    )


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


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.exception('Unhandled exception: %s', e)
    return jsonify({'error': 'An unexpected error occurred'}), 500


# ── Run ───────────────────────────────────────────────────────────────────────

init_db()  # runs on every startup (local dev & PythonAnywhere WSGI)

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, port=5000)
