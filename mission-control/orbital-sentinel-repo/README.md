# Orbital Sentinel

Research prototype for monitoring low-Earth-orbit shell stability against
the Kessler-syndrome tipping point. Frontend is done. Backend is the
current work.

## Layout

```
orbital-sentinel/
├── CLAUDE.md                    ← read this first if you are Claude Code
├── ORBITAL_SENTINEL_SPEC.md     ← API contract (derived from frontend)
├── README.md                    ← this file
├── frontend/                    ← static HTML/JSX prototype (done)
│   ├── Orbital Sentinel - Mission Control.html
│   ├── app.jsx
│   ├── scene.js
│   ├── styles.css
│   ├── tweaks-panel.jsx
│   └── data/
│       └── shell_current_state.json
└── backend/                     ← FastAPI service (TODO)
    ├── CLAUDE.md
    ├── README.md
    └── (your code here)
```

## Quickstart

### Frontend (already works)

```bash
cd frontend
python -m http.server 8080
# open http://localhost:8080/Orbital%20Sentinel%20-%20Mission%20Control.html
```

The frontend defaults to reading the cached JSON at
`frontend/data/shell_current_state.json`. To point it at your live
backend, click the gear icon (Tweaks), enable "Try live /api/live", and
set the API base URL to `http://localhost:8000`.

### Backend (build this)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app:app --reload --port 8000
```

## Working with Claude Code

```bash
cd orbital-sentinel/    # ← important: cd INTO this folder, not above it
claude
```

The first prompt should be:

> Read CLAUDE.md and ORBITAL_SENTINEL_SPEC.md. Confirm the API
> contract, list any ambiguities, then propose a minimal FastAPI scaffold
> in backend/. Do not write code yet.

## Why this is set up the way it is

- `CLAUDE.md` is scoped to *this* folder. Run `claude` from here and the
  agent only sees instructions for this project, even if you have other
  projects sitting next to it in `~/projects/`.
- The specification file has a distinctive name
  (`ORBITAL_SENTINEL_SPEC.md`) so it cannot collide with a `SPEC.md` from
  another repo.
- `backend/CLAUDE.md` is a sub-scoped file with backend-only conventions
  (test layout, dependency policy). It only activates when working in
  `backend/`.

## Status

- ✅ Frontend visualization
- ✅ Mock data fixture
- ✅ API contract documented
- ⬜ Backend `/api/live` endpoint
- ⬜ Space-Track.org integration
- ⬜ `/api/base` (bifurcation curves)
- ⬜ `/api/scenario` (what-if engine)
- ⬜ Deploy
