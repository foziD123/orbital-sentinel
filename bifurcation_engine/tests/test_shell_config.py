"""Unit tests for :mod:`bifurcation_engine.src.shell_config`.

Covers Task 1 acceptance criteria plus VALIDATION.md T2.6
(``delta_D > delta_S`` must hold or :class:`ValueError` is raised).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bifurcation_engine.src.shell_config import (
    DEFAULT_PATH,
    ShellConfig,
    default_shells,
    load_shell_by_name,
    load_shell_defaults,
)


# ---------------------------------------------------------------------------
# ShellConfig construction
# ---------------------------------------------------------------------------


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    """Baseline Shell_B-like parameters; override individual fields per test."""
    base: dict[str, object] = {
        "shell_name": "Shell_B_800km",
        "altitude_km": 800.0,
        "L": 100.0,
        "delta_S": 0.005,
        "delta_D": 0.02,
        "beta": 1.5e-5,
        "gamma": 1.5e-7,
    }
    base.update(overrides)
    return base


def test_valid_construction_ok() -> None:
    shell = ShellConfig(**_valid_kwargs())  # type: ignore[arg-type]

    assert shell.shell_name == "Shell_B_800km"
    assert shell.altitude_km == pytest.approx(800.0)
    assert shell.L == pytest.approx(100.0)
    assert shell.delta_D > shell.delta_S
    # Default sweep bounds.
    assert shell.L_sweep_min == 0.0
    assert shell.L_sweep_max is None
    # Fallback is used when L_sweep_max is missing.
    assert shell.effective_L_sweep_max == pytest.approx(1000.0)


def test_frozen_dataclass_is_immutable() -> None:
    shell = ShellConfig(**_valid_kwargs())  # type: ignore[arg-type]
    with pytest.raises(Exception):  # noqa: PT011 — FrozenInstanceError subclass varies
        shell.L = 42.0  # type: ignore[misc]


# --- VALIDATION.md T2.6 -----------------------------------------------------


@pytest.mark.parametrize(
    ("delta_S", "delta_D"),
    [
        (0.05, 0.01),  # classic T2.6 case: delta_D < delta_S
        (0.02, 0.02),  # equal is also rejected (strict inequality)
    ],
)
def test_delta_D_not_greater_than_delta_S_raises(
    delta_S: float, delta_D: float
) -> None:
    with pytest.raises(ValueError, match="delta_D.*delta_S"):
        ShellConfig(**_valid_kwargs(delta_S=delta_S, delta_D=delta_D))  # type: ignore[arg-type]


# --- Negative / zero guards -------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "bad_value", "match"),
    [
        ("altitude_km", 0.0, "altitude_km"),
        ("altitude_km", -100.0, "altitude_km"),
        ("L", -1.0, "L"),
        ("delta_S", -0.001, "delta_S"),
        ("delta_D", -0.5, "delta_D"),
        ("beta", 0.0, "beta"),
        ("beta", -1e-5, "beta"),
        ("gamma", -1e-7, "gamma"),
        ("L_sweep_min", -1.0, "L_sweep_min"),
    ],
)
def test_negative_parameters_raise(
    field_name: str, bad_value: float, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ShellConfig(**_valid_kwargs(**{field_name: bad_value}))  # type: ignore[arg-type]


def test_empty_shell_name_raises() -> None:
    with pytest.raises(ValueError, match="shell_name"):
        ShellConfig(**_valid_kwargs(shell_name=""))  # type: ignore[arg-type]


def test_sweep_max_not_above_min_raises() -> None:
    with pytest.raises(ValueError, match="L_sweep_max"):
        ShellConfig(
            **_valid_kwargs(L_sweep_min=500.0, L_sweep_max=500.0)  # type: ignore[arg-type]
        )


def test_gamma_zero_is_allowed() -> None:
    """gamma=0 disables the Kessler term and is a valid sanity scenario."""
    shell = ShellConfig(**_valid_kwargs(gamma=0.0))  # type: ignore[arg-type]
    assert shell.gamma == 0.0


# ---------------------------------------------------------------------------
# 3-species opt-in (use_3species=True) — Step 1 of the 3-species extension
# ---------------------------------------------------------------------------


def _valid_3species_kwargs(**overrides: object) -> dict[str, object]:
    """Baseline 3-species kwargs with delta_S < delta_R < delta_D and
    beta_SR / beta_RD strictly positive. Override any field per test."""
    base = _valid_kwargs()
    # Pick delta_R as the midpoint of (delta_S, delta_D) to satisfy the
    # ordering constraint by default.
    base.update(
        {
            "delta_R": 0.5 * (base["delta_S"] + base["delta_D"]),  # type: ignore[operator]
            "beta_SR": 2.0 * base["beta"],  # type: ignore[operator]
            "beta_RD": 3.0 * base["beta"],  # type: ignore[operator]
            "use_3species": True,
        }
    )
    base.update(overrides)
    return base


def test_3species_valid_construction_ok() -> None:
    shell = ShellConfig(**_valid_3species_kwargs())  # type: ignore[arg-type]

    assert shell.use_3species is True
    assert shell.delta_S < shell.delta_R < shell.delta_D
    assert shell.beta_SR > 0.0
    assert shell.beta_RD > 0.0


def test_3species_defaults_off_when_not_requested() -> None:
    """Without ``use_3species=True`` the new fields default to no-op zeros."""
    shell = ShellConfig(**_valid_kwargs())  # type: ignore[arg-type]

    assert shell.use_3species is False
    assert shell.delta_R == 0.0
    assert shell.beta_SR == 0.0
    assert shell.beta_RD == 0.0


def test_3species_off_does_not_constrain_new_fields() -> None:
    """``delta_R < delta_S`` is meaningless when use_3species is False, and
    must therefore NOT raise — otherwise existing 2-D consumers that happen
    to set the field for unrelated reasons would break."""
    shell = ShellConfig(
        **_valid_kwargs(  # type: ignore[arg-type]
            delta_R=0.001,  # below delta_S=0.005 — would be illegal in 3-species
            beta_SR=0.0,    # zero — would be illegal in 3-species
            beta_RD=0.0,    # zero — would be illegal in 3-species
            use_3species=False,
        )
    )
    assert shell.delta_R == pytest.approx(0.001)


@pytest.mark.parametrize(
    ("delta_R", "match"),
    [
        (0.005, "delta_R"),     # equal to delta_S — strict inequality required
        (0.002, "delta_R"),     # below delta_S
        (0.02, "delta_R"),      # equal to delta_D
        (0.05, "delta_R"),      # above delta_D
    ],
)
def test_3species_delta_R_outside_band_raises(
    delta_R: float, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ShellConfig(**_valid_3species_kwargs(delta_R=delta_R))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "bad_value", "match"),
    [
        ("beta_SR", 0.0, "beta_SR"),
        ("beta_SR", -1e-5, "beta_SR"),
        ("beta_RD", 0.0, "beta_RD"),
        ("beta_RD", -1e-5, "beta_RD"),
    ],
)
def test_3species_beta_couplings_must_be_positive(
    field_name: str, bad_value: float, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ShellConfig(**_valid_3species_kwargs(**{field_name: bad_value}))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "bad_value", "match"),
    [
        ("delta_R", -0.001, "delta_R"),
        ("beta_SR", -1e-7, "beta_SR"),
        ("beta_RD", -1e-7, "beta_RD"),
    ],
)
def test_3species_fields_reject_negative_even_when_off(
    field_name: str, bad_value: float, match: str
) -> None:
    """Negative values are rejected whether or not 3-species is opted in.
    The conditional rules are about strict positivity / ordering; basic
    non-negativity is universal, mirroring delta_S / delta_D / gamma."""
    with pytest.raises(ValueError, match=match):
        ShellConfig(**_valid_kwargs(**{field_name: bad_value}))  # type: ignore[arg-type]


def test_3species_default_shells_load_as_2D() -> None:
    """The packaged JSON contains no 3-species fields, so default_shells()
    must continue to return 2-D-only configs (use_3species=False)."""
    shells = load_shell_defaults()
    assert all(s.use_3species is False for s in shells)
    assert all(s.delta_R == 0.0 for s in shells)
    assert all(s.beta_SR == 0.0 for s in shells)
    assert all(s.beta_RD == 0.0 for s in shells)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_default_path_points_to_packaged_json() -> None:
    assert DEFAULT_PATH.exists(), (
        f"Expected packaged defaults at {DEFAULT_PATH!s}; did the file move?"
    )


def test_load_shell_defaults_returns_three_shells() -> None:
    shells = load_shell_defaults()

    assert len(shells) == 3
    names = [s.shell_name for s in shells]
    assert names == ["Shell_A_600km", "Shell_B_800km", "Shell_C_1000km"]

    altitudes = [s.altitude_km for s in shells]
    assert altitudes == pytest.approx([600.0, 800.0, 1000.0])


def test_default_shells_wrapper_matches_load_shell_defaults() -> None:
    assert default_shells() == load_shell_defaults()


def test_default_L_mapped_from_L_default() -> None:
    shell_b = load_shell_by_name("Shell_B_800km")
    assert shell_b.L == pytest.approx(100.0)


def test_sweep_bounds_present() -> None:
    shell_b = load_shell_by_name("Shell_B_800km")
    assert shell_b.L_sweep_min == pytest.approx(0.0)
    assert shell_b.L_sweep_max == pytest.approx(1000.0)


def test_load_shell_by_name_unknown_raises() -> None:
    with pytest.raises(KeyError) as excinfo:
        load_shell_by_name("Shell_Z_nonexistent")

    message = str(excinfo.value)
    # Error message should list the names that DO exist so users can debug.
    assert "Shell_A_600km" in message
    assert "Shell_B_800km" in message
    assert "Shell_C_1000km" in message


def test_load_shell_defaults_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_shell_defaults(missing)


def test_load_shell_defaults_missing_required_key_raises(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    # delta_D omitted entirely.
    bad_json.write_text(
        json.dumps(
            {
                "shells": [
                    {
                        "shell_name": "BrokenShell",
                        "altitude_km": 700,
                        "L_default": 50,
                        "delta_S": 0.01,
                        "beta": 1e-5,
                        "gamma": 1e-7,
                    }
                ]
            }
        )
    )
    with pytest.raises(KeyError, match="delta_D"):
        load_shell_defaults(bad_json)


def test_load_shell_defaults_unknown_key_warns(tmp_path: Path) -> None:
    bad_json = tmp_path / "extra.json"
    bad_json.write_text(
        json.dumps(
            {
                "shells": [
                    {
                        "shell_name": "ExtraKeyShell",
                        "altitude_km": 700,
                        "L_default": 50,
                        "delta_S": 0.005,
                        "delta_D": 0.02,
                        "beta": 1e-5,
                        "gamma": 1e-7,
                        "mystery_field": "unexpected",
                    }
                ]
            }
        )
    )
    with pytest.warns(UserWarning, match="mystery_field"):
        shells = load_shell_defaults(bad_json)

    assert len(shells) == 1
    assert shells[0].shell_name == "ExtraKeyShell"


def test_load_shell_defaults_no_shells_key_raises(tmp_path: Path) -> None:
    bad_json = tmp_path / "no_shells.json"
    bad_json.write_text(json.dumps({"metadata": {}}))
    with pytest.raises(KeyError, match="shells"):
        load_shell_defaults(bad_json)
