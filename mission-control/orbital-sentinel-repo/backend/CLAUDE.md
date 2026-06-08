# Backend — Working Notes

Sub-scoped CLAUDE.md. The parent `../CLAUDE.md` still applies; this
file adds backend-only conventions.

## Stack

- Python 3.11+
- FastAPI + uvicorn
- httpx for outbound HTTP (Space-Track)
- Pydantic v2 for response models
- pytest + pytest-asyncio for tests
- ruff for lint, mypy --strict for types

## Layout (target)

```
backend/
├── pyproject.toml
├── app.py               ← FastAPI() instance; import routers
├── routers/
│   ├── live.py          ← GET /api/live
│   ├── base.py          ← GET /api/base
│   └── scenario.py      ← POST /api/scenario
├── services/
│   ├── spacetrack.py    ← outbound to Space-Track.org
│   ├── shells.py        ← S/D binning + L_fold logic
│   └── cache.py         ← in-memory TTL cache
├── models.py            ← Pydantic response models
├── settings.py          ← env-var config (Space-Track creds, etc.)
└── tests/
    ├── conftest.py
    ├── test_live.py
    ├── test_base.py
    └── test_scenario.py
```

## Conventions

- Every router file exposes a single `router = APIRouter(prefix="/api")`.
- Response models live in `models.py` and are referenced from
  `response_model=...` on every endpoint.
- Never use `dict` as a response type — always a Pydantic model so the
  OpenAPI schema stays accurate.
- Field names match the spec EXACTLY — `S`, `D`, `L_current`, etc.
  Use `model_config = ConfigDict(populate_by_name=True)` if you need
  Python-friendly aliases internally.

## Secrets

`backend/.env` (gitignored):
```
SPACETRACK_USER=...
SPACETRACK_PASS=...
```

If either is unset, `/api/live` returns the cached fixture with
`cached: true`. Do NOT fail-hard on missing credentials — the
frontend depends on graceful degradation.

## Test policy

- Every endpoint has at least one test that asserts the response
  matches the JSON fixture exactly.
- Space-Track calls in tests must be mocked via `respx` or
  `pytest-httpx`. No live network calls in CI.
