# Backend

FastAPI service for Orbital Sentinel. See `../ORBITAL_SENTINEL_SPEC.md`
for the API contract and `CLAUDE.md` for working conventions.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add Space-Track credentials (optional)
```

## Run

```bash
uvicorn app:app --reload --port 8000
```

OpenAPI docs at http://localhost:8000/docs

## Test

```bash
pytest
```
