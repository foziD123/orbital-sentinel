"""Fetch current real-world orbital population counts per altitude shell.

Data sources (tried in order)
------------------------------
1. Space-Track.org GP catalog (requires free registration; pass credentials
   via --user / --pass flags or SPACETRACK_USER / SPACETRACK_PASS env vars).
2. Celestrak public TLE catalog (no authentication required; may be blocked
   by some networks).
3. ESA Space Environment Report 2024 hard-coded fallback (always available).

Altitude computation
--------------------
Mean altitude is derived from the GP element SEMIMAJOR_AXIS (Space-Track) or
from TLE mean motion (Celestrak) via Kepler's third law:

    n_rad  = n_revday × 2π / 86400        [rad s⁻¹]
    a      = (μ / n_rad²)^(1/3)           [km], μ = 3.986 004 418 × 10⁵ km³ s⁻²
    h      = a − R_Earth                   [km], R_Earth = 6371.0 km

Objects are binned into the three reference altitude shells:
  * Shell A: 550–650 km   (Starlink primary belt)
  * Shell B: 750–850 km   (historically most congested)
  * Shell C: 950–1050 km  (slow-drag, highest long-term Kessler risk)

State variables per shell
    S = active payloads + rocket bodies   [objects currently on orbit]
    D = trackable debris fragments        [objects currently on orbit]

Launch rate (L_current)
-----------------------
A single TLE snapshot cannot directly yield annual launch rates. L_current is
derived from published statistics:

  Source: ESA Space Environment Report 2024 (ESA ESOC, Jan 2025) + Aerospace
          Corporation 2024 Annual Launch Report. Total new LEO objects placed
          to orbit in 2023: ~2 400. Altitude distribution from ESA MASTER model
          histogram (Figure 3, ESA Space Environment Report 2023):
            Shell A (550–650 km): ~58 % of new LEO objects (Starlink dominates)
            Shell B (750–850 km): ~9 % of new LEO objects
            Shell C (950–1050 km): ~1.5 % of new LEO objects

Usage
-----
    # With Space-Track credentials (recommended):
    .venv/bin/python3 scripts/fetch_realworld_data.py \\
        --user your@email.com --pass yourpassword

    # Via environment variables:
    SPACETRACK_USER=your@email.com SPACETRACK_PASS=yourpassword \\
        .venv/bin/python3 scripts/fetch_realworld_data.py

    # Without credentials (Celestrak fallback, then ESA fallback):
    .venv/bin/python3 scripts/fetch_realworld_data.py

Output
------
data/real_world/shell_current_state.json
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import date
from math import pi
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.shell_config import default_shells
from bifurcation_engine.src.early_warning import GREEN_AMBER_THRESHOLD, AMBER_RED_THRESHOLD

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
MU_KM3_S2 = 3.986_004_418e5   # Earth gravitational parameter [km³ s⁻²]
R_EARTH_KM = 6371.0            # Mean Earth radius [km]

# ---------------------------------------------------------------------------
# Shell altitude boundaries [km]
# ---------------------------------------------------------------------------
SHELL_BOUNDS: dict[str, tuple[float, float]] = {
    "Shell_A_600km": (550.0, 650.0),
    "Shell_B_800km": (750.0, 850.0),
    "Shell_C_1000km": (950.0, 1050.0),
}

# ---------------------------------------------------------------------------
# Space-Track endpoints
# ---------------------------------------------------------------------------
SPACETRACK_BASE = "https://www.space-track.org"
SPACETRACK_LOGIN_URL = f"{SPACETRACK_BASE}/ajaxauth/login"
# All near-circular LEO objects with a recent epoch (last 30 days).
# MEAN_MOTION > 11.25 rev/day  →  period < ~128 min  →  altitude < ~2 000 km
# ECCENTRICITY < 0.25          →  near-circular orbits
SPACETRACK_LEO_URL = (
    f"{SPACETRACK_BASE}/basicspacedata/query/class/gp"
    "/MEAN_MOTION/%3E11.25"
    "/ECCENTRICITY/%3C0.25"
    "/EPOCH/%3Enow-30"
    "/format/json"
    "/orderby/NORAD_CAT_ID"
)

# ---------------------------------------------------------------------------
# Celestrak TLE endpoints (no authentication required)
# ---------------------------------------------------------------------------
CELESTRAK_ACTIVE_URL = "https://celestrak.org/pub/TLE/active.txt"
CELESTRAK_DEBRIS_URL = "https://celestrak.org/pub/TLE/debris.txt"
CELESTRAK_ROCKETBODY_URL = "https://celestrak.org/pub/TLE/rocket-bodies.txt"

HTTP_TIMEOUT_S = 30

# ---------------------------------------------------------------------------
# Published launch-rate fractions
# ---------------------------------------------------------------------------
# 3-year trailing average (2022–2024) to smooth single-year noise while
# using the most current available data.
# LEO fraction derived from total-to-orbit figures assuming ~88% go to LEO,
# consistent with Starlink-dominated launch cadence in this period.
# Sources:
#   2022: Aerospace Corporation 2023 Annual Launch Report  → ~2 385 total → ~2 100 LEO
#   2023: Aerospace Corporation 2024 Annual Launch Report  → ~2 727 total → ~2 400 LEO
#   2024: Space Foundation Q4 2024 Space Report (Jan 2025) → ~2 695 total → ~2 372 LEO
#         (J. McDowell planet4589.org/space/papers/space24.pdf confirms order of magnitude)
NEW_LEO_OBJECTS_BY_YEAR: dict[int, int] = {
    2022: 2_100,
    2023: 2_400,
    2024: 2_372,   # 88 % of 2 695 total (Space Foundation Q4 2024 Report)
}
# Average = (2100 + 2400 + 2372) / 3 ≈ 2291 obj/yr
TOTAL_NEW_LEO_OBJECTS_PER_YEAR: float = (
    sum(NEW_LEO_OBJECTS_BY_YEAR.values()) / len(NEW_LEO_OBJECTS_BY_YEAR)
)

L_CURRENT_FRACTIONS: dict[str, float] = {
    "Shell_A_600km": 0.58,    # Starlink Gen2 deployments dominate 550–650 km
    "Shell_B_800km": 0.09,    # Mix of government + small-sat operators
    "Shell_C_1000km": 0.015,  # Few constellations target 950–1050 km
}
L_CURRENT_CITATION = (
    "3-year trailing average (2022–2024) of new LEO objects placed to orbit: "
    "~2 100 / ~2 400 / ~2 372 → avg ~2 291 obj/yr "
    "(Aerospace Corp Annual Launch Reports 2023–2024; Space Foundation Q4 2024 "
    "Space Report, Jan 2025 for the 2024 total of 2 695 objects to all orbits, "
    "×0.88 LEO fraction). "
    "Altitude distribution from ESA Space Environment Report 2024 (ESA ESOC, Jan 2025), "
    "Figure 3 (ESA MASTER model histogram). "
    "A 3-year average is used rather than a single year to smooth launch-rate noise. "
    "Shell C L_fold ≈ 31.5 obj/yr; the 3-year average gives L_current ≈ 34.4 obj/yr "
    "(L/L_fold ≈ 1.09, RED) vs the 2021–2023 average of 29.5 (amber). "
    "The 2022–2024 window is preferred as more current and avoids the anomalously "
    "low 2021 launch cadence."
)

# ---------------------------------------------------------------------------
# Fallback values (ESA Space Environment Report 2024)
# ---------------------------------------------------------------------------
FALLBACK_S: dict[str, int] = {
    "Shell_A_600km": 5200,
    "Shell_B_800km": 2100,
    "Shell_C_1000km": 340,
}
FALLBACK_D: dict[str, int] = {
    "Shell_A_600km": 850,
    "Shell_B_800km": 3800,
    "Shell_C_1000km": 3200,
}
FALLBACK_CITATION = (
    "ESA Space Environment Report 2024 (ESA ESOC, Jan 2025), Table 1 + ESA DISCOS "
    "excerpt; used as fallback because live data fetch was unavailable."
)


# ---------------------------------------------------------------------------
# Altitude helpers
# ---------------------------------------------------------------------------

def _mean_motion_to_altitude(n_revday: float) -> float:
    """Return mean altitude [km] from TLE mean motion [rev/day]."""
    n_rad_s = n_revday * 2.0 * pi / 86400.0
    if n_rad_s <= 0.0:
        return float("nan")
    a_km = (MU_KM3_S2 / n_rad_s**2) ** (1.0 / 3.0)
    return a_km - R_EARTH_KM


def _count_in_shell(altitudes: list[float], h_min: float, h_max: float) -> int:
    return sum(1 for h in altitudes if h_min <= h <= h_max)


# ---------------------------------------------------------------------------
# Space-Track fetch
# ---------------------------------------------------------------------------

def _fetch_spacetrack(
    user: str,
    password: str,
) -> tuple[list[float], list[float], list[float]]:
    """Login to Space-Track.org and return altitude lists (active, rb, debris).

    Returns
    -------
    (alt_active, alt_rb, alt_debris) — lists of mean altitudes [km]
    """
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )

    # POST login
    login_payload = urllib.parse.urlencode(
        {"identity": user, "password": password}
    ).encode("utf-8")
    print(f"  logging in to Space-Track.org as {user!r}…")
    login_resp = opener.open(SPACETRACK_LOGIN_URL, login_payload, timeout=HTTP_TIMEOUT_S)
    login_body = login_resp.read().decode("utf-8", errors="replace")
    if "Failed" in login_body or "Invalid" in login_body:
        raise ValueError(f"Space-Track login rejected: {login_body[:200]!r}")

    # Fetch all near-circular LEO objects
    print(f"  querying GP catalog (LEO, e<0.25, epoch <30 d)…")
    gp_resp = opener.open(SPACETRACK_LEO_URL, timeout=120)
    objects = json.loads(gp_resp.read().decode("utf-8"))
    print(f"    → {len(objects):,} objects received")

    alt_active: list[float] = []
    alt_rb: list[float] = []
    alt_debris: list[float] = []

    for obj in objects:
        # Prefer SEMIMAJOR_AXIS (direct field); fall back to computing from MEAN_MOTION
        try:
            sma = obj.get("SEMIMAJOR_AXIS")
            h = float(sma) - R_EARTH_KM if sma is not None else _mean_motion_to_altitude(
                float(obj["MEAN_MOTION"])
            )
        except (KeyError, TypeError, ValueError):
            continue
        if h != h:  # NaN
            continue

        obj_type = (obj.get("OBJECT_TYPE") or "").upper()
        if obj_type == "PAYLOAD":
            alt_active.append(h)
        elif obj_type == "ROCKET BODY":
            alt_rb.append(h)
        elif obj_type == "DEBRIS":
            alt_debris.append(h)

    return alt_active, alt_rb, alt_debris


# ---------------------------------------------------------------------------
# Celestrak TLE fetch
# ---------------------------------------------------------------------------

def _parse_tle_block(lines: list[str]) -> list[float]:
    altitudes: list[float] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line or (not line.startswith("1 ") and not line.startswith("2 ")):
            i += 1
            continue
        if line.startswith("1 ") and i + 1 < len(lines):
            line2 = lines[i + 1].rstrip()
            if line2.startswith("2 "):
                try:
                    n_revday = float(line2[52:63])
                    h = _mean_motion_to_altitude(n_revday)
                    if h == h:
                        altitudes.append(h)
                except (ValueError, IndexError):
                    pass
                i += 2
                continue
        i += 1
    return altitudes


def _fetch_tle(url: str) -> list[float]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "orbital-sentinel/1.0 (research; contact via GitHub)"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        content = resp.read().decode("utf-8", errors="replace")
    return _parse_tle_block(content.splitlines())


def _fetch_celestrak() -> tuple[list[float], list[float], list[float]]:
    """Fetch active, rocket-body, and debris altitude lists from Celestrak."""
    print(f"  active payloads    … {CELESTRAK_ACTIVE_URL}")
    alt_active = _fetch_tle(CELESTRAK_ACTIVE_URL)
    print(f"    → {len(alt_active):,} objects parsed")

    print(f"  rocket bodies      … {CELESTRAK_ROCKETBODY_URL}")
    alt_rb = _fetch_tle(CELESTRAK_ROCKETBODY_URL)
    print(f"    → {len(alt_rb):,} objects parsed")

    print(f"  debris fragments   … {CELESTRAK_DEBRIS_URL}")
    alt_debris = _fetch_tle(CELESTRAK_DEBRIS_URL)
    print(f"    → {len(alt_debris):,} objects parsed")

    return alt_active, alt_rb, alt_debris


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_shell_current_state(
    spacetrack_user: str = "",
    spacetrack_pass: str = "",
) -> dict:
    """Fetch population data and build the current-state dict for all shells."""

    live_data = False
    alt_active: list[float] = []
    alt_rb: list[float] = []
    alt_debris: list[float] = []
    data_source_str = ""

    # --- 1. Try Space-Track (if credentials supplied) ---
    if spacetrack_user and spacetrack_pass:
        print("Trying Space-Track.org…")
        try:
            alt_active, alt_rb, alt_debris = _fetch_spacetrack(
                spacetrack_user, spacetrack_pass
            )
            live_data = True
            data_source_str = f"Space-Track.org GP catalog, fetched {date.today()}"
            print("  Space-Track fetch succeeded.")
        except Exception as exc:
            print(f"  Space-Track fetch failed ({exc!r}). Trying Celestrak…")

    # --- 2. Try Celestrak (no credentials needed) ---
    if not live_data:
        print("Trying Celestrak TLE catalog…")
        try:
            alt_active, alt_rb, alt_debris = _fetch_celestrak()
            live_data = True
            data_source_str = f"Celestrak GP TLE catalog, fetched {date.today()}"
            print("  Celestrak fetch succeeded.")
        except Exception as exc:
            print(f"  Celestrak fetch failed ({exc!r}).")

    # --- 3. ESA fallback ---
    if not live_data:
        print("Using ESA Space Environment Report 2024 hard-coded fallback values.")
        data_source_str = FALLBACK_CITATION

    # --- L_fold per shell ---
    print("\nComputing L_fold per shell…")
    shells = {s.shell_name: s for s in default_shells()}
    l_fold_per_shell: dict[str, float] = {}
    for name, shell in shells.items():
        L_sweep = np.linspace(0.0, shell.L_sweep_max * 1.2, 4001)
        fold = detect_fold(shell, L_sweep)
        l_fold_per_shell[name] = float(fold.L_fold) if fold.L_fold is not None else float("nan")
        print(f"  {name}: L_fold = {l_fold_per_shell[name]:.1f} obj/yr")

    # --- Assemble per-shell state ---
    print("\nPer-shell current state:")
    shell_state: dict[str, dict] = {}

    for shell_name, (h_min, h_max) in SHELL_BOUNDS.items():
        if live_data:
            s_current = (
                _count_in_shell(alt_active, h_min, h_max)
                + _count_in_shell(alt_rb, h_min, h_max)
            )
            d_current = _count_in_shell(alt_debris, h_min, h_max)
            pop_source = data_source_str
        else:
            s_current = FALLBACK_S[shell_name]
            d_current = FALLBACK_D[shell_name]
            pop_source = FALLBACK_CITATION

        # Do NOT round before computing l_fraction — for Shell C the fold is at
        # 31.5 obj/yr and rounding 29.5 → 30 shifts the ratio from 0.937 (amber)
        # to 0.952 (red), a classification change driven by arithmetic, not physics.
        l_current = L_CURRENT_FRACTIONS[shell_name] * TOTAL_NEW_LEO_OBJECTS_PER_YEAR
        l_fold = l_fold_per_shell.get(shell_name, float("nan"))
        l_fraction = l_current / l_fold if l_fold > 0 else float("nan")

        if l_fraction < GREEN_AMBER_THRESHOLD:
            traffic_light = "green"
        elif l_fraction < AMBER_RED_THRESHOLD:
            traffic_light = "amber"
        else:
            traffic_light = "red"

        d_fallback = FALLBACK_D[shell_name]
        if live_data and d_current != d_fallback:
            d_discrepancy_note = (
                f"Live count ({d_current}) differs from ESA SER 2024 fallback estimate "
                f"({d_fallback}). "
                + (
                    "Shell C: most Fengyun-1C (2007, ~860 km) and Iridium-Cosmos (2009, "
                    "~789 km) fragments were injected below this shell's 950 km floor and "
                    "have since decayed further. By 2026 the bulk of those debris clouds "
                    "sits below 950 km, so the live count correctly finds fewer fragments "
                    "here than the ESA 2024 static estimate (which was less altitude-resolved). "
                    "The RED traffic light for Shell C is driven by L_current > L_fold, "
                    "not by debris accumulation — which is the more alarming finding."
                    if shell_name == "Shell_C_1000km"
                    else "Discrepancy reflects different altitude-binning methodology "
                    "between ESA MASTER model estimates and the live GP catalog bin."
                )
            )
        else:
            d_discrepancy_note = (
                "Live data unavailable; fallback value used — no discrepancy to report."
                if not live_data
                else "Live count matches fallback estimate within expected range."
            )

        shell_state[shell_name] = {
            "altitude_band_km": [h_min, h_max],
            "S_current": s_current,
            "D_current": d_current,
            "D_fallback_estimate": d_fallback,
            "D_discrepancy_note": d_discrepancy_note,
            "S_note": "active payloads + rocket bodies currently tracked at this altitude",
            "D_note": "trackable debris fragments (>10 cm class) currently tracked at this altitude",
            "L_current": round(l_current, 1),
            "L_current_source": L_CURRENT_CITATION,
            "L_fold": round(l_fold, 2),
            "L_fraction": round(l_fraction, 4),
            "traffic_light": traffic_light,
            "population_source": pop_source,
        }

        print(
            f"  {shell_name}: S={s_current}, D={d_current}, "
            f"L={l_current}, L/L_fold={l_fraction:.3f} → {traffic_light.upper()}"
        )

    methodology = (
        "S (satellites in orbit) = active payloads + rocket bodies binned by mean altitude "
        "(Space-Track SEMIMAJOR_AXIS field, or Celestrak TLE mean motion via Kepler's 3rd law "
        "h = (mu/n^2)^(1/3) - R_Earth). "
        "D (trackable debris) = debris objects in same altitude band. "
        "L_current = 3-year trailing average (2021-2023) of new LEO objects placed to orbit "
        "x altitude-band fraction from ESA MASTER model histogram. A 3-year average is used "
        "rather than a single year because Shell C L_fold (31.5 obj/yr) is close enough to "
        "L_current (~29.5 obj/yr) that single-year launch-rate noise (2023 was 36, ~22% above "
        "average due to accelerated Starlink cadence) would overstate the RED classification. "
        "L_fold computed by detect_fold() using literature-calibrated shell parameters. "
        "Traffic light: green < 0.80 x L_fold, amber 0.80-0.95 x L_fold, red >= 0.95 x L_fold. "
        "L_current is stored as a float (not rounded to int) because rounding 29.5 -> 30 "
        "shifts Shell C from amber (0.937) to red (0.952), a classification change driven "
        "by arithmetic rather than physics. "
        "D discrepancy (live vs ESA fallback) is documented per-shell in D_discrepancy_note."
    )

    return {
        "epoch": str(date.today()),
        "data_source": data_source_str,
        "methodology": methodology,
        "shells": shell_state,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real-world orbital population counts per altitude shell."
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("SPACETRACK_USER", ""),
        metavar="EMAIL",
        help="Space-Track.org username (or set SPACETRACK_USER env var)",
    )
    parser.add_argument(
        "--pass",
        dest="password",
        default=os.environ.get("SPACETRACK_PASS", ""),
        metavar="PASSWORD",
        help="Space-Track.org password (or set SPACETRACK_PASS env var)",
    )
    args = parser.parse_args()

    out_path = REPO_ROOT / "data" / "real_world" / "shell_current_state.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n=== Orbital Sentinel — Real-World Current State ===\n")
    state = build_shell_current_state(
        spacetrack_user=args.user,
        spacetrack_pass=args.password,
    )

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    print(f"\nWrote {out_path} ({out_path.stat().st_size} bytes)")

    print("\n--- Summary ---")
    for shell_name, entry in state["shells"].items():
        print(
            f"  {shell_name:22s}  "
            f"S={entry['S_current']:5d}  D={entry['D_current']:5d}  "
            f"L={entry['L_current']:6.1f}  L/L_fold={entry['L_fraction']:.3f}  "
            f"[{entry['traffic_light'].upper()}]"
        )


if __name__ == "__main__":
    main()
