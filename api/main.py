"""FastAPI application for the Orbital Sentinel Module 2+3.

Endpoints:
  GET  /api/health          → liveness probe
  GET  /api/base            → pre-computed base data for all shells
  POST /api/whatif          → compute what-if scenario for all three shells
  DELETE /api/whatif/clear  → clear all scenario overlays
  GET  /api/live            → live shell state (Space-Track with cached fallback)

All three shells are computed in a single /api/whatif call.
Maximum 5 overlays — HTTP 400 after that until /api/whatif/clear is called.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine_bridge import compute_whatif

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERLAY_COLORS = ["#E76F51", "#2A9D8F", "#E9C46A", "#9B5DE5", "#F72585"]
MAX_OVERLAYS = 5

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = REPO_ROOT / "frontend" / "data"

# ---------------------------------------------------------------------------
# In-memory scenario store (single-user, single-process — demo day only)
# ---------------------------------------------------------------------------

_scenarios: list[dict] = []

# ---------------------------------------------------------------------------
# Live data cache — avoids frontend 3-second timeout on Space-Track queries
# ---------------------------------------------------------------------------

_live_cache: dict | None = None          # last successful live result
_live_cache_ts: float = 0.0              # epoch seconds when it was fetched
_LIVE_TTL = 1800.0                        # 30 min TTL
_refresh_lock = threading.Lock()
_refresh_running = False


def _background_refresh() -> None:
    """Fetch Space-Track in a background thread and update _live_cache."""
    global _live_cache, _live_cache_ts, _refresh_running
    try:
        result = _live_spacetrack_query()
        _live_cache = result
        _live_cache_ts = time.monotonic()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        _refresh_running = False


def _trigger_refresh() -> None:
    global _refresh_running
    with _refresh_lock:
        if _refresh_running:
            return
        _refresh_running = True
    t = threading.Thread(target=_background_refresh, daemon=True)
    t.start()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WhatIfRequest(BaseModel):
    L_multiplier: float = Field(1.0, ge=0.1, le=10.0,
        description="Scale real-world L_current per shell. 1.0 = no change.")
    debris_removal_rate: float = Field(0.0, ge=0.0, le=100.0,
        description="Active debris removal in objects/yr.")
    gamma_multiplier: float = Field(1.0, ge=0.1, le=10.0,
        description="Scale cascade coefficient gamma. 1.0 = no change.")
    label: str = Field("Custom scenario", max_length=80,
        description="Human-readable label for this overlay.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Pre-warm the Space-Track cache at startup so the first browser request is fast.
    import os
    if os.environ.get("SPACETRACK_USER") and os.environ.get("SPACETRACK_PASS"):
        print("[orbital-sentinel] Starting Space-Track prefetch…")
        _trigger_refresh()
    yield

app = FastAPI(
    title="Orbital Sentinel — Scenario Simulator API",
    description="Module 2 what-if scenario API. Computes bifurcation curves for all three LEO shells.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # demo day: single laptop, no auth needed
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Serve the Claude Design Mission Control frontend at /mission-control/
_MC_DIR = REPO_ROOT / "mission-control" / "orbital-sentinel-repo" / "frontend"
if _MC_DIR.exists():
    app.mount("/mission-control", StaticFiles(directory=str(_MC_DIR), html=True), name="mission-control")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_static(filename: str) -> Any:
    """Load a pre-computed JSON file from frontend/data/."""
    path = FRONTEND_DATA / filename
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Static file {filename} not found. "
                "Run scripts/export_frontend_data.py first."
            ),
        )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "overlays": len(_scenarios), "max_overlays": MAX_OVERLAYS}


@app.get("/api/base")
def get_base() -> dict:
    """Return pre-computed base data for all shells.

    Normally the frontend loads these directly from static JSON files.
    This endpoint is a fallback for environments where static files
    cannot be served alongside the HTML page.
    """
    return {
        "base_curves": _load_static("base_curves.json"),
        "shell_current_state": _load_static("shell_current_state.json"),
        "indicator_curves": _load_static("indicator_curves.json"),
    }


@app.post("/api/whatif")
def post_whatif(req: WhatIfRequest) -> dict:
    """Compute a what-if scenario for all three shells in one call.

    Returns the new bifurcation curves, fold location, and traffic-light
    status for each shell, plus the overlay colour assigned to this scenario.

    HTTP 400 if 5 overlays are already active — call DELETE /api/whatif/clear
    to reset.
    """
    if len(_scenarios) >= MAX_OVERLAYS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum {MAX_OVERLAYS} overlays reached. "
                "Call DELETE /api/whatif/clear before adding more."
            ),
        )

    shells = compute_whatif(
        L_multiplier=req.L_multiplier,
        debris_removal_rate=req.debris_removal_rate,
        gamma_multiplier=req.gamma_multiplier,
    )

    color = OVERLAY_COLORS[len(_scenarios)]
    scenario = {
        "label": req.label,
        "color": color,
        "L_multiplier": req.L_multiplier,
        "debris_removal_rate": req.debris_removal_rate,
        "gamma_multiplier": req.gamma_multiplier,
        "shells": shells,
    }
    _scenarios.append(scenario)

    return scenario


@app.delete("/api/whatif/clear")
def delete_clear() -> dict:
    """Clear all active scenario overlays.

    The frontend should reset all overlay curves and traffic lights to the
    base state after calling this endpoint.
    """
    count = len(_scenarios)
    _scenarios.clear()
    return {"cleared": count, "overlays": 0}


@app.get("/api/whatif/scenarios")
def get_scenarios() -> dict:
    """Return the list of currently active scenarios (for state recovery)."""
    return {"scenarios": _scenarios, "count": len(_scenarios)}


# ---------------------------------------------------------------------------
# Module 3: Live shell state endpoint
# ---------------------------------------------------------------------------

# Shell altitude bounds for Space-Track binning
_SHELL_BOUNDS = {
    "Shell_A_600km": (550, 650),
    "Shell_B_800km": (750, 850),
    "Shell_C_1000km": (950, 1050),
}
_SHELL_KEYS = {"Shell_A_600km": "A", "Shell_B_800km": "B", "Shell_C_1000km": "C"}

# Launch rate fractions per shell from ESA SER 2024 / Aerospace Corp 2024
# (3-year trailing average 2022-2024: ~2291 new LEO objects/yr)
_LEO_AVG_PER_YR = 2291.0
_LAUNCH_FRACS = {"Shell_A_600km": 0.58, "Shell_B_800km": 0.09, "Shell_C_1000km": 0.015}
_GREEN_AMBER = 0.80
_AMBER_RED   = 0.95


def _trend_arrow(L_current: float, shell_name: str) -> str:
    """Approximate trend: compare current 3-yr avg to older 2-yr avg (2022-2023).

    Uses documented annual LEO launch counts:
      2022: ~2100, 2023: ~2400 → 2-yr avg = 2250 obj/yr
      3-yr avg (2022-2024): ~2291 obj/yr
    If 3-yr avg > 2-yr avg by >5% → increasing; <-5% → decreasing; else stable.
    """
    older_avg = 2250.0
    frac = _LAUNCH_FRACS[shell_name]
    L_older = older_avg * frac
    if L_current > L_older * 1.05:
        return "↑ increasing"
    if L_current < L_older * 0.95:
        return "↓ decreasing"
    return "→ stable"


def _classify(l_fraction: float) -> str:
    if l_fraction < _GREEN_AMBER:
        return "green"
    if l_fraction < _AMBER_RED:
        return "amber"
    return "red"


def _cached_shell_state(reason: str) -> dict:
    """Load cached snapshot and annotate as fallback."""
    cached_path = REPO_ROOT / "data" / "real_world" / "shell_current_state.json"
    if not cached_path.exists():
        cached_path = FRONTEND_DATA / "shell_current_state.json"
    with cached_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    shells_out: dict = {}
    for name, key in _SHELL_KEYS.items():
        s = raw["shells"][name]
        L_current = float(s["L_current"])
        L_fold    = float(s["L_fold"])
        l_frac    = L_current / L_fold
        shells_out[key] = {
            "S": int(s["S_current"]),
            "D": int(s["D_current"]),
            "L_current": round(L_current, 1),
            "L_fold": round(L_fold, 1),
            "L_fraction": round(l_frac, 4),
            "traffic_light": _classify(l_frac),
            "trend": _trend_arrow(L_current, name),
        }

    return {
        "retrieved_utc": raw.get("epoch", "unknown"),
        "source": raw.get("data_source", "cached snapshot"),
        "cached": True,
        "fallback_reason": reason,
        "shells": shells_out,
    }


def _live_spacetrack_query() -> dict:
    """Query Space-Track.org GP catalog, bin by altitude, return shell state.

    Requires SPACETRACK_USER and SPACETRACK_PASS environment variables.
    Raises RuntimeError if credentials are absent or query fails.
    """
    import os

    user = os.environ.get("SPACETRACK_USER", "")
    pwd  = os.environ.get("SPACETRACK_PASS", "")
    if not user or not pwd:
        raise RuntimeError("SPACETRACK_USER / SPACETRACK_PASS not set")

    MU = 3.986004418e5  # km³/s²
    RE = 6371.0          # km

    import math

    base = "https://www.space-track.org"
    login_url  = f"{base}/ajaxauth/login"
    logout_url = f"{base}/ajaxauth/logout"
    # Filter by apogee in LEO band (500–1200 km covers all three shells).
    # No predicates clause — not supported by Space-Track API.
    query_url = (
        f"{base}/basicspacedata/query/class/gp"
        f"/APOAPSIS/500--1200"
        f"/DECAY_DATE/null-val"
        f"/format/json/emptyresult/show"
    )

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    # Login
    login_data = urllib.parse.urlencode({"identity": user, "password": pwd}).encode()
    opener.open(login_url, login_data, timeout=30)

    # Fetch LEO band catalog
    resp = opener.open(query_url, timeout=120)
    catalog = json.loads(resp.read())

    opener.open(logout_url, timeout=10)

    MU = 3.986004418e5  # km³/s²
    RE = 6371.0

    def _altitude(obj: dict) -> float:
        """Mean altitude in km. Use APOAPSIS/PERIAPSIS if present, else MEAN_MOTION."""
        try:
            apoapsis  = float(obj["APOAPSIS"])
            periapsis = float(obj["PERIAPSIS"])
            if apoapsis > 0 and periapsis > 0:
                return (apoapsis + periapsis) / 2.0
        except (KeyError, TypeError, ValueError):
            pass
        # Fallback: compute from MEAN_MOTION (rev/day)
        n_rpd = float(obj["MEAN_MOTION"])
        n_rps = n_rpd * 2.0 * math.pi / 86400.0
        a = (MU / n_rps ** 2) ** (1.0 / 3.0)
        return a - RE

    # Bin by altitude
    shell_counts: dict[str, dict] = {
        name: {"S": 0, "D": 0} for name in _SHELL_BOUNDS
    }

    for obj in catalog:
        try:
            alt   = _altitude(obj)
            otype = str(obj.get("OBJECT_TYPE", "")).upper()
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue

        for name, (lo, hi) in _SHELL_BOUNDS.items():
            if lo <= alt <= hi:
                if otype == "DEBRIS":
                    shell_counts[name]["D"] += 1
                else:
                    shell_counts[name]["S"] += 1
                break

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    shells_out: dict = {}
    for name, key in _SHELL_KEYS.items():
        S = shell_counts[name]["S"]
        D = shell_counts[name]["D"]
        L_current = round(_LEO_AVG_PER_YR * _LAUNCH_FRACS[name], 1)
        # Use cached L_fold (engine-computed, not re-run on every query)
        cached = _cached_shell_state("fold lookup")
        L_fold = cached["shells"][key]["L_fold"]
        l_frac = L_current / L_fold
        shells_out[key] = {
            "S": S,
            "D": D,
            "L_current": L_current,
            "L_fold": L_fold,
            "L_fraction": round(l_frac, 4),
            "traffic_light": _classify(l_frac),
            "trend": _trend_arrow(L_current, name),
        }

    return {
        "retrieved_utc": now_utc,
        "source": "Space-Track.org GP catalog (live)",
        "cached": False,
        "shells": shells_out,
    }


@app.get("/api/live/debug")
def get_live_debug() -> dict:
    """Debug endpoint: returns first 3 raw objects from Space-Track to inspect field names."""
    import os, math
    user = os.environ.get("SPACETRACK_USER", "")
    pwd  = os.environ.get("SPACETRACK_PASS", "")
    if not user or not pwd:
        return {"error": "No credentials set"}

    base = "https://www.space-track.org"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    login_data = urllib.parse.urlencode({"identity": user, "password": pwd}).encode()
    opener.open(f"{base}/ajaxauth/login", login_data, timeout=30)

    # Minimal query: 3 objects only, no altitude filter
    query_url = f"{base}/basicspacedata/query/class/gp/limit/3/format/json/emptyresult/show"
    resp = opener.open(query_url, timeout=30)
    sample = json.loads(resp.read())
    return {"count": len(sample), "sample": sample}


@app.get("/api/live")
def get_live() -> dict:
    """Return live shell state from Space-Track, falling back to cached snapshot.

    Uses a 30-minute in-memory cache so repeated calls return instantly and
    the frontend's 3-second timeout is never a problem after warm-up.

    On a cold cache: returns the static snapshot immediately and kicks off a
    background Space-Track fetch. On the next call (a few seconds later) the
    live data will be ready.

    Credentials: set SPACETRACK_USER and SPACETRACK_PASS environment variables
    before starting the server. They are never exposed to the browser.
    """
    import os
    has_creds = bool(os.environ.get("SPACETRACK_USER")) and bool(os.environ.get("SPACETRACK_PASS"))

    # Serve from cache if fresh
    age = time.monotonic() - _live_cache_ts
    if _live_cache is not None and age < _LIVE_TTL:
        return _live_cache

    # Cache is stale or empty — trigger a background refresh
    if has_creds:
        _trigger_refresh()

    # Return whatever we have: stale live data beats static snapshot
    if _live_cache is not None:
        stale = dict(_live_cache)
        stale["cache_age_s"] = round(age)
        return stale

    return _cached_shell_state("Space-Track fetch in progress — retry in ~60 s" if has_creds else "No credentials")
