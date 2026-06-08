# Orbital Sentinel — Claude Code Working Notes

## Scope

This CLAUDE.md applies to the `orbital-sentinel/` project only. If you are
working inside any other folder, ignore this file.

In bounds:
- `frontend/` — static HTML + JSX prototype (do not rewrite into a framework)
- `backend/`  — Python/FastAPI service you will build
- `data/`     — shared sample payloads (frontend + backend both read these)

Out of bounds:
- Anything outside this folder (sibling projects in the parent directory)
- Do not modify `frontend/` aesthetics or layout — only swap fetch URLs
- Do not edit `data/shell_current_state.json` — it is the API contract fixture

## What this project is

A research prototype for visualizing the stability of low-Earth-orbit
shells (600 / 800 / 1000 km). The frontend is finished. Your job is to
build the backend that serves live data in the shape the frontend already
consumes.

## Architecture

```
┌─────────────────┐     HTTP/JSON      ┌─────────────────┐
│  frontend/      │ ◀───────────────── │  backend/       │
│  static HTML    │   GET /api/live    │  FastAPI :8000  │
│  React via CDN  │   GET /api/base    │  Python 3.11+   │
│  Three.js scene │   POST /api/scenario│  uvicorn        │
└─────────────────┘                     └─────────────────┘
                                                ▲
                                                │ fetch (cron / on-demand)
                                                ▼
                                    ┌────────────────────────┐
                                    │ Space-Track.org GP cat │
                                    │ ESA SER fallback       │
                                    └────────────────────────┘
```

## Read first

Before you write any code, read these in order:

1. `ORBITAL_SENTINEL_SPEC.md` — full API contract derived from the frontend
2. `data/shell_current_state.json` — canonical response shape, exact field names
3. `frontend/app.jsx` lines ~810–870 — the `loadData()` effect that calls
   `/api/live` and maps fields. **Field names there are the source of truth.**
4. `backend/CLAUDE.md` — backend-specific conventions (lives in that folder)

## Field-name contract (do not rename)

The frontend reads these exact keys from `/api/live`:

```
shells.{A,B,C}.S              integer
shells.{A,B,C}.D              integer
shells.{A,B,C}.L_current      float
shells.{A,B,C}.L_fold         float
shells.{A,B,C}.L_fraction     float
shells.{A,B,C}.traffic_light  "green" | "amber" | "red"
cached                        boolean
retrieved_utc                 ISO-8601 string
```

Note: `/api/live` uses short keys (`S`, `D`) while the cached snapshot at
`data/shell_current_state.json` uses long keys (`S_current`, `D_current`).
This asymmetry is intentional — see the spec for why. **Do not "fix" it.**

## Working style

- One endpoint at a time, fully working, before starting the next.
- Generate Pydantic models from the JSON fixture first; everything else
  flows from those types.
- Every endpoint must have at least one pytest case using the fixture as
  the expected output.
- `uvicorn backend.app:app --reload --port 8000` is the dev command.
- When the frontend needs to talk to the backend, the user toggles
  "Try live /api/live" in the Tweaks panel — you do not edit any JSX.

## What not to do

- ❌ Do not introduce a database. Cache in memory with a TTL.
- ❌ Do not add authentication. This is a research tool on localhost.
- ❌ Do not rewrite the frontend in Next.js / Vite / anything.
- ❌ Do not invent new shell altitudes. A/B/C are fixed at 600/800/1000 km.
- ❌ Do not change field names to be more "Pythonic". The contract wins.

## Definition of done (phase 1)

- `GET /api/live` returns the exact shape the frontend expects
- Live data is fetched from Space-Track (or stubbed if creds absent)
- Frontend "Try live /api/live" toggle works without code changes
- `pytest` is green
- README.md has a `make dev` quickstart that boots both sides
