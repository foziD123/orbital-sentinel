"""Shell configuration: parameters for a single orbital altitude band.

Implements Task 1 of Module 1 (see TASKS.md and CLAUDE.md). A :class:`ShellConfig`
bundles the dynamical parameters of the Kessler-syndrome model plus the
altitude metadata needed to interpret them, and validates that the values are
physically meaningful on construction.

The default 2-D model (per shell)::

    S_dot = L - delta_S * S - beta * S * D
    D_dot = beta * S * D + gamma * D**2 - delta_D * D

where ``L`` is the bifurcation parameter (launch rate). See ``CLAUDE.md`` for
the full derivation.

The optional 3-species extension (opt-in via ``use_3species=True``) adds a
derelict population ``R``::

    S_dot = L - delta_S * S - beta * S * D - beta_SR * S * R
    R_dot = delta_S * S - delta_R * R - beta_RD * R * D
    D_dot = beta * S * D + beta_SR * S * R + beta_RD * R * D
            + gamma * D**2 - delta_D * D

The new parameters ``delta_R``, ``beta_SR``, ``beta_RD`` default to zero so
all 2-D consumers continue to load existing JSON shells unchanged. When
``use_3species`` is set, additional validation is enforced; see
:meth:`ShellConfig.__post_init__`.

A loader is provided for the packaged ``data/parameters/shell_defaults.json``
so downstream modules can obtain the three reference shells (A, B, C) without
hard-coding numbers.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import MISSING, dataclass, fields
from pathlib import Path
from typing import Any

__all__ = [
    "ShellConfig",
    "DEFAULT_PATH",
    "load_shell_defaults",
    "load_shell_by_name",
    "default_shells",
]


# Resolve the packaged JSON relative to the repository root.
# shell_config.py lives at <repo>/bifurcation_engine/src/shell_config.py, so
# parents[2] is the repo root.
DEFAULT_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "parameters" / "shell_defaults.json"
)


@dataclass(frozen=True)
class ShellConfig:
    """Parameters for one altitude shell of the Kessler bifurcation model.

    All rates are in units of ``1/year``; ``L`` is in ``objects/year``; ``beta``
    and ``gamma`` are in ``1/(objects*year)``. See ``data/parameters/shell_defaults.json``
    for the canonical literature-derived values.

    Validation rules enforced in :meth:`__post_init__`:

    * ``delta_D > delta_S`` — debris must decay faster than satellites at any
      altitude where this model is physically meaningful (see CLAUDE.md).
    * All rates and coupling constants are non-negative.
    * ``beta > 0`` — a zero collision cross-section removes the satellite-debris
      coupling entirely, which is not a shell we want to reason about.
    * ``altitude_km > 0``.
    * If ``L_sweep_max`` is given it must exceed ``L_sweep_min``.
    * When ``use_3species`` is True, the additional 3-species fields must be
      physically consistent: ``delta_S < delta_R < delta_D`` (derelicts sit
      between active satellites and debris in their drag timescale) and
      ``beta_SR > 0``, ``beta_RD > 0`` (otherwise the new collision channels
      are inactive and the 3-species model degenerates to the 2-D one).

    A :class:`ValueError` is raised on any violation, naming the offending field.
    """

    shell_name: str
    altitude_km: float
    L: float
    delta_S: float
    delta_D: float
    beta: float
    gamma: float
    delta_R: float = 0.0
    beta_SR: float = 0.0
    beta_RD: float = 0.0
    use_3species: bool = False
    L_sweep_min: float = 0.0
    L_sweep_max: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.shell_name:
            raise ValueError("shell_name must be a non-empty string")

        if self.altitude_km <= 0:
            raise ValueError(
                f"altitude_km must be positive (got {self.altitude_km!r})"
            )

        if self.L < 0:
            raise ValueError(f"L (launch rate) must be non-negative (got {self.L!r})")

        if self.delta_S < 0:
            raise ValueError(
                f"delta_S (satellite decay) must be non-negative (got {self.delta_S!r})"
            )

        if self.delta_D < 0:
            raise ValueError(
                f"delta_D (debris decay) must be non-negative (got {self.delta_D!r})"
            )

        # Core physical constraint: debris decays faster than satellites.
        # This is the primary validation covered by VALIDATION.md T2.6.
        if self.delta_D <= self.delta_S:
            raise ValueError(
                "delta_D must be strictly greater than delta_S "
                f"(got delta_S={self.delta_S!r}, delta_D={self.delta_D!r}); "
                "debris fragments deorbit faster than active satellites at any "
                "altitude where this model is physically meaningful."
            )

        if self.beta <= 0:
            raise ValueError(
                f"beta (collision cross-section) must be positive (got {self.beta!r})"
            )

        if self.gamma < 0:
            raise ValueError(
                f"gamma (Kessler cascade coefficient) must be non-negative "
                f"(got {self.gamma!r})"
            )

        # The 3-species fields default to zero (no-op for the 2-D model).
        # We always reject negative values so the constraints below are
        # symmetric with delta_S / beta / gamma; the additional ordering and
        # positivity rules only kick in when use_3species is opted into.
        if self.delta_R < 0:
            raise ValueError(
                f"delta_R (derelict decay) must be non-negative "
                f"(got {self.delta_R!r})"
            )
        if self.beta_SR < 0:
            raise ValueError(
                f"beta_SR (active-derelict collision rate) must be non-negative "
                f"(got {self.beta_SR!r})"
            )
        if self.beta_RD < 0:
            raise ValueError(
                f"beta_RD (derelict-debris collision rate) must be non-negative "
                f"(got {self.beta_RD!r})"
            )

        if self.use_3species:
            if not (self.delta_S < self.delta_R < self.delta_D):
                raise ValueError(
                    "When use_3species is True, the derelict decay rate must "
                    "satisfy delta_S < delta_R < delta_D "
                    f"(got delta_S={self.delta_S!r}, delta_R={self.delta_R!r}, "
                    f"delta_D={self.delta_D!r}); derelicts deorbit slower than "
                    "fragments but faster than active satellites."
                )
            if self.beta_SR <= 0:
                raise ValueError(
                    "When use_3species is True, beta_SR (active-derelict "
                    f"collision rate) must be positive (got {self.beta_SR!r})"
                )
            if self.beta_RD <= 0:
                raise ValueError(
                    "When use_3species is True, beta_RD (derelict-debris "
                    f"collision rate) must be positive (got {self.beta_RD!r})"
                )

        if self.L_sweep_min < 0:
            raise ValueError(
                f"L_sweep_min must be non-negative (got {self.L_sweep_min!r})"
            )

        if self.L_sweep_max is not None and self.L_sweep_max <= self.L_sweep_min:
            raise ValueError(
                "L_sweep_max must be strictly greater than L_sweep_min "
                f"(got L_sweep_min={self.L_sweep_min!r}, "
                f"L_sweep_max={self.L_sweep_max!r})"
            )

    @property
    def effective_L_sweep_max(self) -> float:
        """Return ``L_sweep_max`` if set, else a sensible fallback of ``10 * L``.

        Downstream continuation code should prefer this over the raw attribute
        so a shell with only ``L`` supplied still has a usable sweep range.
        """
        if self.L_sweep_max is not None:
            return self.L_sweep_max
        # Ensure we always have a non-zero upper bound even if L == 0.
        return max(10.0 * self.L, 1.0)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

# Keys from the JSON that map directly onto ShellConfig fields.
_DIRECT_KEYS: tuple[str, ...] = (
    "shell_name",
    "altitude_km",
    "delta_S",
    "delta_D",
    "beta",
    "gamma",
    "L_sweep_min",
    "L_sweep_max",
    "notes",
)

# The JSON stores the current/default launch rate under "L_default" to make
# it visually obvious that it is a starting point rather than a fixed physical
# constant. Inside the dataclass we call it simply "L".
_JSON_L_KEY = "L_default"


def _build_shell_from_dict(entry: dict[str, Any]) -> ShellConfig:
    """Construct a :class:`ShellConfig` from one JSON entry."""

    shell_name = entry.get("shell_name", "<unknown>")

    if _JSON_L_KEY not in entry:
        raise KeyError(
            f"Shell entry {shell_name!r} is missing required key {_JSON_L_KEY!r}"
        )

    kwargs: dict[str, Any] = {"L": entry[_JSON_L_KEY]}

    for key in _DIRECT_KEYS:
        if key in entry:
            kwargs[key] = entry[key]

    # Fields without defaults on the dataclass are required in the JSON too:
    # shell_name, altitude_km, L, delta_S, delta_D, beta, gamma.
    required = {f.name for f in fields(ShellConfig) if f.default is MISSING}
    missing = required - kwargs.keys()
    if missing:
        raise KeyError(
            f"Shell entry {shell_name!r} is missing required key(s): "
            + ", ".join(sorted(missing))
        )

    known = set(_DIRECT_KEYS) | {_JSON_L_KEY}
    unknown = set(entry) - known
    if unknown:
        warnings.warn(
            f"Shell entry {shell_name!r} has unrecognised key(s) "
            f"{sorted(unknown)!r}; ignoring.",
            stacklevel=3,
        )

    return ShellConfig(**kwargs)


def load_shell_defaults(path: str | Path = DEFAULT_PATH) -> list[ShellConfig]:
    """Load every shell defined in a ``shell_defaults.json``-style file.

    Parameters
    ----------
    path:
        Location of the JSON file. Defaults to the packaged
        ``data/parameters/shell_defaults.json``.

    Returns
    -------
    list[ShellConfig]
        Shells in the order they appear in the file.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    KeyError
        If the JSON is missing the ``shells`` list or any entry is missing a
        required field.
    ValueError
        If any entry fails :class:`ShellConfig` validation.
    """
    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"Shell defaults file not found: {json_path!s}")

    with json_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if "shells" not in payload or not isinstance(payload["shells"], list):
        raise KeyError(
            f"{json_path!s} must contain a top-level 'shells' list"
        )

    return [_build_shell_from_dict(entry) for entry in payload["shells"]]


def load_shell_by_name(
    name: str,
    path: str | Path = DEFAULT_PATH,
) -> ShellConfig:
    """Return the single shell whose ``shell_name`` matches ``name``.

    Raises
    ------
    KeyError
        If no shell with that name exists in the file. The error message
        lists all available names to make debugging trivial.
    """
    shells = load_shell_defaults(path)
    for shell in shells:
        if shell.shell_name == name:
            return shell

    available = [s.shell_name for s in shells]
    raise KeyError(
        f"No shell named {name!r} in {Path(path)!s}. "
        f"Available shells: {available!r}"
    )


def default_shells() -> list[ShellConfig]:
    """Shorthand for :func:`load_shell_defaults` with the packaged JSON path."""
    return load_shell_defaults(DEFAULT_PATH)
