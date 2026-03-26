# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Tests

```bash
python -m pytest test_app.py -v
# Run a single test class or method:
python -m pytest test_app.py::TestRegister::test_register_success -v

# Security-focused tests:
python -m pytest test_security.py -v
```

Tests use Flask's test client with a fresh isolated SQLite temp file per test (no external server needed). 30 tests cover auth, matches, billing, premium schema, and static routes. `test_security.py` covers additional security scenarios.

**Windows note:** SQLite file locks may prevent temp file cleanup after tests — this is harmless, the OS reclaims them on reboot.

**Known gotcha:** Never run two test processes simultaneously against the same DB file — SQLite will deadlock. Each test creates its own temp file to avoid this.

## Running the App

**With Flask backend (full features — auth, match history):**
```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

**Standalone frontend only:** Open `index.html` directly in a browser — no server required, but auth/history features will be unavailable.

## Architecture

The app has two layers:

**Frontend** — HTML pages served by Flask:
- `home.html` — landing/marketing page (`/home`)
- `index.html` — main SPA with Tracker, Stats, and Insights views (`/`)
- `login.html` — registration and login forms (`/login`)
- `profile.html` — match history and account settings for authenticated users (`/profile`)

**Backend** — `app.py` (Flask + SQLite):
- Serves all static files
- Handles user auth via server-side sessions
- Stores match history in `tennis.db`

**PWA** — `manifest.json`, `sw.js`, `icon.svg` enable installable PWA with offline support.

### Frontend SPA (index.html + script.js)

Three tabs controlled by `showView(viewId)`:
1. **Tracker** (`#view-tracker`) — Real-time point entry via a 3-step flow: serve type → outcome (win/loss) → shot method
2. **Stats** (`#view-stats`) — Aggregated match statistics
3. **Insights** (`#view-insights`) — Practice plan generated from match stats

All frontend state is in global variables in `script.js`:
- `matchConfig` — pre-match settings (player name, sets, games per set, tiebreak rules, deuce/advantage)
- `player1/2Points/Games/Sets` — live score
- `stats` — object tracking wins/losses by shot type
- `isServing`, `currentServeType`, `inTiebreak`, `tiebreakPointCount` — serve/tiebreak state

### Scoring Flow

Point entry goes through steps 0→1→2:
- Step 0: Select serve type (1st serve, 2nd serve, or double fault)
- Step 1: Select outcome (won/lost)
- Step 2: Select shot method (from `WIN_METHODS` or `LOSS_METHODS` arrays)

`updateScore()` handles standard tennis scoring, game/set/match progression, tiebreak logic, and serving switches.

### Practice Plan Generation

`generateInsights()` analyzes the `stats` object, identifies top weaknesses/strengths, and maps them to entries in the `DRILLS` object (13+ error types, each with 2-3 drills, durations, and coaching cues). Requires at least 5 tracked points.

### Backend API (app.py)

Auth endpoints (no auth required):
- `POST /api/auth/register` — create account (rate-limited: 10/hour)
- `POST /api/auth/login` — start session (rate-limited: 20/hour)
- `POST /api/auth/logout` — clear session
- `GET /api/auth/me` — check session (returns `username`, `first_name`, `last_name`, `is_premium`, `subscription_status`)
- `POST /api/auth/forgot-password` — send password reset email (rate-limited: 5/hour); always returns 200 to avoid user enumeration
- `POST /api/auth/reset-password` — consume a reset token and set new password (body: `{token, password}`)

Auth endpoints (`@login_required`):
- `PUT /api/auth/profile` — update username, first_name, last_name
- `POST /api/auth/change-password` — change password (body: `{current_password, new_password}`)
- `DELETE /api/auth/account` — permanently delete account and all matches, then clear session

Match endpoints (`@login_required`):
- `GET /api/matches` — fetch user's match history (ordered by `id DESC` — newest first)
- `GET /api/matches/export` — download match history as CSV
- `POST /api/matches` — save a completed match (body: `{config, stats, result}`)

Billing endpoints (Stripe):
- `POST /api/billing/checkout` — create Stripe Checkout session; returns `{url}`
- `POST /api/billing/portal` — open Stripe customer portal; returns `{url}`
- `POST /api/billing/webhook` — Stripe webhook handler (no auth); sets `is_premium` based on subscription status

### Database Schema

`tennis.db` (SQLite, created automatically on startup):
- `users(id, username, email, password_hash, is_premium, stripe_customer_id, subscription_status, first_name, last_name, created_at)` — new columns are added via migration in `init_db()` so old DBs are upgraded automatically
- `matches(id, user_id, config, stats, result, played_at)` — `config`/`stats`/`result` stored as JSON strings
- `reset_tokens(id, user_id, token, expires_at, used)` — one-time password reset tokens, expire after 1 hour

### Stripe / Billing

Billing is optional — the app runs without it, returning 503 on billing endpoints. To enable, set these environment variables:
- `STRIPE_SECRET_KEY` — Stripe secret key
- `STRIPE_PRICE_ID` — recurring price ID for the premium subscription
- `STRIPE_WEBHOOK_SECRET` — for webhook signature verification

### Password Reset / Email

Password reset emails are optional. To enable, set:
- `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` — SMTP credentials
- `APP_BASE_URL` — base URL used in reset links (default `http://localhost:5000`)

Without SMTP config, forgot-password requests are accepted but no email is sent (silent no-op logged as a warning).

### Demo Data

`seed.py` creates two demo accounts with realistic match history:

```bash
python seed.py
```

| Account | Email | Password |
|---|---|---|
| Free | carlos@demo.com | tennis123 |
| Premium | serena@demo.com | tennis123 |

Re-running `seed.py` is idempotent — it updates existing users and replaces their matches.

### Deployment

Designed for PythonAnywhere WSGI at `fymc.pythonanywhere.com`. `init_db()` is called at module level (not inside `__main__`) so it runs under both local dev and WSGI. Secret key is persisted in `.secret_key` file or via `SECRET_KEY` environment variable. Set `FLASK_DEBUG=true` to enable Flask debug mode locally.

To deploy updates:
```bash
# On PythonAnywhere bash console:
cd tennis-analist && git pull origin main
# Then click Reload on the Web tab.
```
