import os
import json
import secrets
import sqlite3
from functools import wraps

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

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


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


# ── Auth API ──────────────────────────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data     = request.get_json() or {}
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
def login():
    data     = request.get_json() or {}
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
    return jsonify({
        'authenticated': True,
        'user_id':  session['user_id'],
        'username': session['username'],
    })


# ── Matches API ───────────────────────────────────────────────────────────────

@app.route('/api/matches', methods=['GET'])
@login_required
def get_matches():
    conn = get_db()
    rows = conn.execute(
        'SELECT id, config, stats, result, played_at FROM matches '
        'WHERE user_id = ? ORDER BY played_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/matches', methods=['POST'])
@login_required
def save_match():
    data = request.get_json() or {}
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


# ── Run ───────────────────────────────────────────────────────────────────────

init_db()  # runs on every startup (local dev & PythonAnywhere WSGI)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
