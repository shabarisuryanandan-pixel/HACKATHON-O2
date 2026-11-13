# Project Ground Rules (`HACKATHON O2`)

> **Flexibility Note**: These are the default working rules for this repository. Anything here can be adapted or changed whenever the problem statement or project requirements call for it.

## 1. Tech Stack
- **Backend**: Python + FastAPI + Uvicorn
- **Frontend**: HTML5 + Tailwind CSS + Vanilla JavaScript (with Chart.js and interactive SVG where useful)
- **Persistence**: SQLite + Supabase
- **Automation**: Optional n8n webhooks
- **Hosting & CI/CD**: GitHub (`main`) -> Render auto-deploy

## 2. UI & Design Rules
- Do **not** lock in any colors or UI theme prematurely; choose the visual style and palette based on the problem statement.
- **No emojis** anywhere in the website UI, text, cards, buttons, logs, or code.
- Use clean, classy, minimal typography (avoid robotic or terminal fonts for general text and numbers).
- Keep tabs, cards, and views **manual on click**; do not add auto-switching timers or opening splash animations unless explicitly requested.

## 3. Engineering & Quality Rules
- Never change backend calculation or business logic when asked for UI or visual changes.
- Use parameterized SQL queries whenever using SQLite.
- Keep all secrets in `.env` (never commit `.env` to GitHub) and always maintain `.gitignore`.
- Before pushing any code, always run automated checks: verify all routes return HTTP 200 and run all tests in `tests/` using FastAPI `TestClient`.
- After verified changes, commit cleanly and push to `main` so Render auto-deploys.

## 4. Presentation & Judge Mindset
- Keep every solution practical, privacy-safe, and secure (isolated networks, authenticated APIs, manual overrides where relevant).
- Explain technical and real-world concepts in simple, plain English.
