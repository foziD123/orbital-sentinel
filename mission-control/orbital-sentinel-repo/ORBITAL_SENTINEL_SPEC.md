# Orbital Sentinel — Backend API Specification

This document is derived from reading the finished frontend. Every field
listed here is consumed by `frontend/app.jsx` or `frontend/scene.js`.
If you remove or rename a field, the UI breaks.

## Conventions

- All endpoints under `/api/`
- All responses `application/json; charset=utf-8`
- Shell identifiers: `"A"` (600 km), `"B"` (800 km), `"C"` (1000 km)
- Floats are not rounded server-side (see why under `L_current` below)
- CORS: allow `http://localhost:8080` and `http://127.0.0.1:8080` in dev

## Endpoints

### `GET /api/live`

Returns the current state of all three shells, fetched live from
Space-Track.org and computed against the literature-calibrated
`L_fold` thresholds.

**Response:**

```json
{
  "retrieved_utc": "2026-04-27T14:32:11Z",
  "cached": false,
  "source": "Space-Track.org GP catalog",
  "shells": {
    "A": {
      "S":             2157,
      "D":             541,
      "L_current":     1328.6,
      "L_fold":        25100.1,
      "L_fraction":    0.0529,
      "traffic_light": "green"
    },
    "B": { "S": 620, "D": 2259, "L_current": 206.2, "L_fold": 670.0,  "L_fraction": 0.3077, "traffic_light": "green" },
    "C": { "S": 545, "D": 873,  "L_current": 34.4,  "L_fold": 31.5,   "L_fraction": 1.0908, "traffic_light": "red"   }
  }
}
```

**Behavior:**

- If Space-Track is reachable: fetch GP catalog, bin by `SEMIMAJOR_AXIS`,
  compute `S`/`D` for each shell, return with `cached: false`.
- If Space-Track is down or no credentials: return the seed values from
  `data/shell_current_state.json` with `cached: true`.
- Cache successful live fetches in memory for **15 minutes** to stay
  under Space-Track rate limits.
- Frontend has a **3-second timeout** on this call. Stay well under that.

**Field semantics:**

| Field | Type | Meaning |
|---|---|---|
| `S` | int | Active payloads + rocket bodies in the altitude band |
| `D` | int | Trackable debris fragments (> 10 cm) in the altitude band |
| `L_current` | float | 3-year trailing avg of new objects placed in this shell per year |
| `L_fold` | float | Tipping-point launch rate from `detect_fold()` |
| `L_fraction` | float | `L_current / L_fold` |
| `traffic_light` | enum | `"green"` if < 0.80, `"amber"` if 0.80–0.95, `"red"` if ≥ 0.95 |

> ⚠️ `L_current` MUST be returned as a float, not rounded. Rounding 29.5
> → 30 flips Shell C from amber to red — a classification change driven
> by arithmetic rather than physics. The cached snapshot has a long
> explanation; preserve that behavior.

### `GET /api/base`

Returns the precomputed bifurcation diagram for each shell (stable
branch + unstable branch + fold point). The frontend currently draws
stylized curves locally — once this endpoint exists, swap to it.

**Response:**

```json
{
  "shells": {
    "A": {
      "L_fold": 25100.1,
      "stable_branch":   [[L0, D0], [L1, D1], ...],
      "unstable_branch": [[L0, D0], [L1, D1], ...]
    },
    "B": { ... },
    "C": { ... }
  }
}
```

50–100 points per branch is plenty for HUD-quality sparklines.

### `POST /api/scenario`

What-if engine. Takes scenario parameters, returns per-shell projected
state. The frontend currently computes this client-side as a stopgap
(`applyScenario()` in `app.jsx`); move the math server-side for accuracy.

**Request:**

```json
{
  "L_mult":     2.0,     // launch-rate multiplier, 0.1 – 5.0
  "removal":    0,       // debris removal per year, 0 – 50
  "gamma_mult": 1.0      // cascade coefficient multiplier, 0.5 – 3.0
}
```

**Response:** same shape as `/api/live` but with `cached: true` and a
`scenario_id` field echoing the params.

## Data source notes

- **Space-Track.org**: requires registered account. Read TLEs from
  the GP catalog endpoint. Use `SEMIMAJOR_AXIS` (km from Earth center) →
  subtract Earth radius (6378.137 km) → bin into shell.
- **ESA Space Environment Report 2024**: source for `L_fold` calibration
  and the fallback `D_fallback_estimate` values you see in the cached
  JSON. The numbers in the fixture are correct as of 2026-04-27.
- **Aerospace Corp Annual Launch Report 2024**: source for the 3-year
  trailing launch averages used in `L_current`.

## Open questions for the backend author

1. Do we want to persist historical `S/D/L` snapshots for the time-series
   charts in the Telemetry tab? Currently those sparklines are
   procedurally generated client-side.
2. Should `traffic_light` thresholds be configurable per shell, or are
   the global 0.80 / 0.95 cutoffs universal?
3. Is there appetite for a `/api/stream` SSE endpoint so the UI can
   update without polling?

Discuss with the user before implementing any of these.
