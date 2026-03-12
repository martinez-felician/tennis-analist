# Tennis Analyst

A web-based tennis match tracker and coaching platform. Track points in real time, analyze your stats, and get a personalized practice plan after every match.

## Features

- **Live Match Tracker** — Step-by-step point entry (serve type → outcome → shot method) with full tennis scoring (games, sets, tiebreaks, deuce/advantage)
- **Match Stats** — Aggregated win/loss breakdowns by shot type and serve
- **Practice Insights** — Auto-generated drill plan based on your weaknesses
- **Match History** — Save and review past matches (requires account)
- **Auth** — Register/login with server-side sessions
- **Account Settings** — Update profile and change password
- **Premium Subscriptions** — Stripe-powered billing (optional)
- **PWA** — Installable on mobile, works offline

## Tech Stack

- **Frontend:** Vanilla JS, HTML/CSS (no framework)
- **Backend:** Python / Flask
- **Database:** SQLite
- **Payments:** Stripe (optional)
- **Deployment:** PythonAnywhere (WSGI)

## Running Locally

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

Or open `index.html` directly in a browser for the frontend only (no auth or history).

## Running Tests

```bash
python -m pytest test_app.py -v
```

30 tests covering auth, matches, billing, and static routes.

## Environment Variables (optional)

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Enable Stripe billing |
| `STRIPE_PRICE_ID` | Premium subscription price |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook verification |
| `SECRET_KEY` | Flask session secret (auto-generated if omitted) |
