# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

No build system or package manager. Open `index.html` directly in a browser — no server or dependencies required.

## Architecture

A single-page application (SPA) in three files:

- **`index.html`** — UI structure with three main views: Tracker, Stats, Insights, plus a setup modal
- **`script.js`** — All application logic (~850 lines, vanilla JS, no frameworks)
- **`style.css`** — Styling with CSS custom properties for theming (~950 lines)

### View System

Three tabs controlled by `showView(viewId)`:
1. **Tracker** (`#view-tracker`) — Real-time point entry via a 3-step flow: serve type → outcome (win/loss) → shot method
2. **Stats** (`#view-stats`) — Aggregated match statistics
3. **Insights** (`#view-insights`) — AI-style practice plan generated from match stats

### State

All state lives in global variables in `script.js`:
- `matchConfig` — pre-match settings (player name, sets, games per set, tiebreak rules, deuce/advantage)
- `player1/2Points/Games/Sets` — live score
- `stats` — object tracking wins/losses by shot type
- `isServing`, `currentServeType`, `inTiebreak`, `tiebreakPointCount` — serve/tiebreak state

### Scoring Flow

Point entry goes through steps 0→1→2:
- Step 0: Select serve type (1st serve, 2nd serve, or double fault)
- Step 1: Select outcome (won/lost)
- Step 2: Select shot method (from `WIN_METHODS` or `LOSS_METHODS` arrays)

After each point, `updateScore()` handles standard tennis scoring, game/set/match progression, tiebreak logic, and serving switches.

### Practice Plan Generation

`generateInsights()` analyzes the `stats` object, identifies top weaknesses/strengths, and maps them to entries in the `DRILLS` object (13+ error types, each with 2-3 drills, durations, and coaching cues). Requires at least 5 tracked points.

### Responsive Design

CSS uses media queries and CSS custom properties for layout. Recent work adjusted layouts for laptop vs. phone screen sizes.
