"""
Seed script — creates two demo accounts with realistic match history.

  FREE user  → carlos@demo.com  / tennis123
  PREMIUM user → serena@demo.com  / tennis123

Run with:  python seed.py
"""

import json
import os
import random
import sqlite3
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import app as flask_app

# ── Helpers ───────────────────────────────────────────────────────────────────

random.seed(42)

OPPONENTS = ['Rafael', 'Novak', 'Roger', 'Andy', 'Daniil', 'Jannik', 'Carlos', 'Holger']
CLUBS     = ['Royal Tennis Club', 'Club Náutico TC', 'Palermo TC', 'La Moraleja Club',
             'Real Club de Tenis', 'Club de Campo', 'Argentino TC', 'Montevideo TC']
PHASES    = ['friendly', 'round-robin', 'quarters', 'semis', 'final']
PHASE_W   = [4, 3, 2, 2, 1]   # weights — friendlies most common

WIN_KEYS  = ['ace', 'fh-win', 'bh-win', 'vol', 'oh', 'drop', 'opp-err']
LOSS_KEYS = ['df', 'fh-ue', 'bh-ue', 'fh-fe', 'bh-fe', 'opp-win', 'miss-return', 'vol-err', 'oh-err', 'drop-err']


def rand_stats(skill: float) -> dict:
    """Generate realistic point-level stats.
    skill in [0, 1] — higher = more winners, fewer errors.
    """
    total_points = random.randint(60, 130)
    won   = int(total_points * (0.38 + skill * 0.24))  # 38 – 62 % win rate
    lost  = total_points - won

    # Distribute wins across win keys with weighted randomness
    win_weights  = [0.10, 0.22, 0.14, 0.08, 0.05, 0.06, 0.35]
    loss_weights = [0.08, 0.22, 0.16, 0.10, 0.08, 0.12, 0.10, 0.06, 0.04, 0.04]

    def spread(total, weights):
        counts = [0] * len(weights)
        for _ in range(total):
            i = random.choices(range(len(weights)), weights=weights)[0]
            counts[i] += 1
        return counts

    win_counts  = spread(won,  win_weights)
    loss_counts = spread(lost, loss_weights)

    s = {}
    for key, val in zip(WIN_KEYS,  win_counts):  s[key] = val
    for key, val in zip(LOSS_KEYS, loss_counts): s[key] = val

    # Serve & return stats derived from point counts
    serve_points = random.randint(30, 60)
    s['serve1stIn']  = int(serve_points * (0.55 + skill * 0.15))
    s['serve1stOut'] = serve_points - s['serve1stIn']
    s['serve2ndIn']  = int(s['serve1stOut'] * (0.78 + skill * 0.10))
    s['returnWon']   = int((total_points - serve_points) * (0.35 + skill * 0.15))
    s['returnLost']  = (total_points - serve_points) - s['returnWon']
    return s


def rand_match(player_name: str, skill: float, days_ago: int) -> dict:
    sets_format = random.choice([3, 3, 3, 5])
    sets_needed = (sets_format + 1) // 2
    won = random.random() < (0.38 + skill * 0.24)

    p1_sets = sets_needed if won else random.randint(0, sets_needed - 1)
    p2_sets = sets_needed if not won else random.randint(0, sets_needed - 1)

    played_at = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')

    config = {
        'playerName':       player_name,
        'opponentName':     random.choice(OPPONENTS),
        'clubName':         random.choice(CLUBS),
        'phase':            random.choices(PHASES, weights=PHASE_W)[0],
        'sets':             sets_format,
        'gamesPerSet':      6,
        'deuce':            True,
        'tiebreak':         True,
        'finalSetTiebreak': False,
        'tiebreakLength':   7,
        'startServing':     random.choice([True, False]),
    }

    return {
        'config':    json.dumps(config),
        'stats':     json.dumps(rand_stats(skill)),
        'result':    json.dumps({'won': won, 'player1Sets': p1_sets, 'player2Sets': p2_sets}),
        'played_at': played_at,
    }


# ── Database setup ─────────────────────────────────────────────────────────────

flask_app.init_db()
conn = sqlite3.connect(flask_app.DB_PATH)
conn.row_factory = sqlite3.Row


def create_user(username, email, password, first_name, last_name, is_premium=0):
    try:
        conn.execute(
            '''INSERT INTO users (username, email, password_hash, first_name, last_name,
               is_premium, subscription_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (username, email, generate_password_hash(password),
             first_name, last_name, is_premium,
             'active' if is_premium else None)
        )
        conn.commit()
        print(f'  Created user: {email}')
    except sqlite3.IntegrityError:
        print(f'  User already exists, updating: {email}')
        conn.execute(
            '''UPDATE users SET password_hash=?, first_name=?, last_name=?,
               is_premium=?, subscription_status=? WHERE email=?''',
            (generate_password_hash(password), first_name, last_name,
             is_premium, 'active' if is_premium else None, email)
        )
        conn.commit()
    return conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()['id']


def seed_matches(user_id, player_name, skill, count):
    # Remove old seeded matches for this user so re-runs are idempotent
    conn.execute('DELETE FROM matches WHERE user_id=?', (user_id,))
    conn.commit()
    for i in range(count):
        m = rand_match(player_name, skill, days_ago=i * 6 + random.randint(0, 5))
        conn.execute(
            'INSERT INTO matches (user_id, config, stats, result, played_at) VALUES (?,?,?,?,?)',
            (user_id, m['config'], m['stats'], m['result'], m['played_at'])
        )
    conn.commit()
    print(f'  Seeded {count} matches')


# ── Seed ──────────────────────────────────────────────────────────────────────

print('\n=== Free user ===')
free_id = create_user(
    username   = 'carlos_free',
    email      = 'carlos@demo.com',
    password   = 'tennis123',
    first_name = 'Carlos',
    last_name  = 'Gómez',
    is_premium = 0,
)
seed_matches(free_id, player_name='Carlos', skill=0.42, count=10)

print('\n=== Premium user ===')
prem_id = create_user(
    username   = 'serena_pro',
    email      = 'serena@demo.com',
    password   = 'tennis123',
    first_name = 'Serena',
    last_name  = 'Williams',
    is_premium = 1,
)
seed_matches(prem_id, player_name='Serena', skill=0.72, count=14)

conn.close()

print()
print('Done! Login credentials')
print('-----------------------------------------')
print('FREE     carlos@demo.com  / tennis123')
print('PREMIUM  serena@demo.com  / tennis123')
print('-----------------------------------------')
