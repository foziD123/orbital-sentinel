"""Configuration for the split-decay Hopf-hunt experiment (quarantined).

This module is the parameter-object for a fully additive experiment that tests
whether physically separating two satellite fates can unlock a genuine Hopf
bifurcation in the 3-species Kessler model. The existing 2-D and 3-species
pipelines do not import or depend on anything in this module; the experiment
is opt-in by *constructing* a :class:`SplitDecayConfig` rather than by
toggling a flag on :class:`ShellConfig`.

The split. The production model uses a single rate ``delta_S`` for all
satellite outflow. The experiment splits that into two physically distinct
channels:

* ``kappa_S`` — controlled disposal / deorbit; the satellite leaves the
  orbital system entirely.
* ``rho_S``  — failure or retirement into the derelict state; the satellite
  remains in orbit as ``R``.

The total outflow from ``S`` is preserved (``kappa_S + rho_S == delta_S`` of
the underlying shell) so the experiment is directly comparable to the
existing 3-species results.

Yield multipliers. Each collision channel that *creates* debris is given a
fragment-yield multiplier ``eta`` that scales how many debris fragments are
produced per collision event. ``eta_SD = 1`` is the baseline (matches the
existing 3-species model exactly); derelict collisions are typically more
energetic and produce more fragments, so the validation enforces
``eta >= 1`` on all three channels but does not impose any ordering — the
sweep driver explores ``(eta_SD, eta_SR, eta_RD)`` triplets such as
``(1, 2, 5)``.

The full ODE that consumes a :class:`SplitDecayConfig` is implemented in
:mod:`bifurcation_engine.src.model_split`. The corresponding 3x3 Jacobian
is in :mod:`bifurcation_engine.src.eigenvalues_split`. See the project plan
for the closed-form derivation.

Note on the ``R_dot`` correction. The split-decay model includes the term
``-beta_SR * S * R`` in ``R_dot`` (i.e. the derelict body *is* removed in an
active-derelict collision). This is the physically realistic version of the
collision channel and a deliberate departure from the existing 3-species
model's documented asymmetry. See the plan for the analytical consequences
on the trace inequality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shell_config import ShellConfig

__all__ = [
    "SplitDecayConfig",
]


# Tolerance for the kappa_S + rho_S == delta_S conservation check.
# Made relative to delta_S so very small literature decay rates (Shell C has
# delta_S = 1e-3 / yr) still get a meaningful tolerance band.
_OUTFLOW_REL_TOL = 1e-9
_OUTFLOW_ABS_TOL = 1e-15


@dataclass(frozen=True)
class SplitDecayConfig:
    """Parameters for one altitude shell under the split-decay experiment.

    All rates are in ``1/year``; ``L`` is in ``objects/year``; ``beta_*`` are
    in ``1/(objects*year)``; ``eta_*`` are dimensionless fragment-yield
    multipliers.

    Validation rules enforced in :meth:`__post_init__` (every violation
    raises :class:`ValueError` and names the offending field):

    * ``shell_name`` is non-empty; ``altitude_km > 0``; ``L >= 0``.
    * ``kappa_S > 0`` and ``rho_S > 0``. Fully-deorbited or fully-failed
      satellites are explicitly excluded so the split is always genuine —
      use ``rho_S = 0.999 * delta_S`` if you want to *approach* the
      no-deorbit limit, but ``rho_S = delta_S`` exactly is rejected.
    * ``delta_S = kappa_S + rho_S`` and ``delta_S < delta_R < delta_D``
      (consistent with the 3-species ordering: derelicts deorbit faster than
      active satellites but slower than fragments).
    * ``beta_SD > 0``, ``beta_SR > 0``, ``beta_RD > 0``.
    * ``eta_SD >= 1.0``, ``eta_SR >= 1.0``, ``eta_RD >= 1.0``. Yields cannot
      go below the baseline cross-section accounting.
    * ``gamma >= 0``.
    * ``L_sweep_max > L_sweep_min`` when ``L_sweep_max`` is set.

    The computed property :attr:`delta_S` returns ``kappa_S + rho_S`` and is
    the value the original 2-D / 3-species shell would have used.
    """

    shell_name: str
    altitude_km: float
    L: float

    kappa_S: float
    rho_S: float

    delta_R: float
    delta_D: float

    beta_SD: float
    beta_SR: float
    beta_RD: float

    gamma: float

    eta_SD: float = 1.0
    eta_SR: float = 1.0
    eta_RD: float = 1.0

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
            raise ValueError(
                f"L (launch rate) must be non-negative (got {self.L!r})"
            )

        # The split must be genuine on both sides.
        if self.kappa_S <= 0:
            raise ValueError(
                "kappa_S (controlled-deorbit rate) must be strictly positive "
                f"(got {self.kappa_S!r}); use a small positive value to "
                "approach the no-deorbit limit instead of zero."
            )
        if self.rho_S <= 0:
            raise ValueError(
                "rho_S (failure rate into derelict) must be strictly "
                f"positive (got {self.rho_S!r}); use a small positive value "
                "to approach the no-failure limit instead of zero."
            )

        delta_S = self.kappa_S + self.rho_S

        if self.delta_R <= delta_S:
            raise ValueError(
                "delta_R must be strictly greater than delta_S = "
                f"kappa_S + rho_S (got delta_R={self.delta_R!r}, "
                f"delta_S={delta_S!r}); derelicts deorbit slower than active "
                "satellites."
            )

        if self.delta_D <= self.delta_R:
            raise ValueError(
                "delta_D must be strictly greater than delta_R "
                f"(got delta_R={self.delta_R!r}, delta_D={self.delta_D!r}); "
                "fragments deorbit faster than derelicts."
            )

        if self.beta_SD <= 0:
            raise ValueError(
                f"beta_SD (sat-debris collision rate) must be positive "
                f"(got {self.beta_SD!r})"
            )
        if self.beta_SR <= 0:
            raise ValueError(
                f"beta_SR (sat-derelict collision rate) must be positive "
                f"(got {self.beta_SR!r})"
            )
        if self.beta_RD <= 0:
            raise ValueError(
                f"beta_RD (derelict-debris collision rate) must be positive "
                f"(got {self.beta_RD!r})"
            )

        if self.gamma < 0:
            raise ValueError(
                f"gamma (Kessler self-cascade) must be non-negative "
                f"(got {self.gamma!r})"
            )

        for name, value in (
            ("eta_SD", self.eta_SD),
            ("eta_SR", self.eta_SR),
            ("eta_RD", self.eta_RD),
        ):
            if value < 1.0:
                raise ValueError(
                    f"{name} (fragment yield multiplier) must satisfy "
                    f"{name} >= 1.0 (got {value!r}); yields below the "
                    "baseline cross-section have no physical meaning here."
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
    def delta_S(self) -> float:
        """Total outflow rate from S (matches the original shell's delta_S)."""
        return self.kappa_S + self.rho_S

    @property
    def effective_L_sweep_max(self) -> float:
        """``L_sweep_max`` if set, else ``10 * L`` with a floor of 1.0."""
        if self.L_sweep_max is not None:
            return self.L_sweep_max
        return max(10.0 * self.L, 1.0)

    @classmethod
    def from_shell(
        cls,
        shell: "ShellConfig",
        *,
        rho_fraction: float,
        delta_R: float | None = None,
        beta_SR: float | None = None,
        beta_RD: float | None = None,
        eta_SD: float = 1.0,
        eta_SR: float = 1.0,
        eta_RD: float = 1.0,
        gamma_multiplier: float = 1.0,
    ) -> "SplitDecayConfig":
        """Build a split-decay config from an existing 2-D :class:`ShellConfig`.

        Parameters
        ----------
        shell:
            The base 2-D shell configuration. Its ``delta_S``, ``delta_D``,
            ``beta`` (taken as ``beta_SD``), ``gamma``, ``L``, sweep bounds
            and metadata are inherited; ``shell.use_3species`` is ignored.
        rho_fraction:
            Fraction of ``shell.delta_S`` allocated to the failure channel
            ``rho_S``. Must satisfy ``0 < rho_fraction < 1`` (the boundary
            values 0 and 1 are rejected because both sides of the split must
            be genuine — see the validation rules on :class:`SplitDecayConfig`).
            ``kappa_S`` is set to ``(1 - rho_fraction) * shell.delta_S`` so
            ``kappa_S + rho_S == shell.delta_S`` exactly (modulo floating
            point, which the conservation check tolerates).
        delta_R, beta_SR, beta_RD:
            Optional overrides. When ``None`` the defaults from the existing
            3-species recipe are used:
            ``delta_R = 0.5 * (shell.delta_S + shell.delta_D)``,
            ``beta_SR = 2 * shell.beta``, ``beta_RD = 3 * shell.beta``.
        eta_SD, eta_SR, eta_RD:
            Fragment yield multipliers. Defaults are ``1.0`` (baseline
            equivalent to the existing 3-species model on this axis).
        gamma_multiplier:
            Linear multiplier applied to ``shell.gamma``. The sweep driver
            uses this axis to probe the moderate-cascade regime.

        Returns
        -------
        SplitDecayConfig
            A fully validated config. Raises :class:`ValueError` from
            :meth:`__post_init__` if any field is out of range.
        """
        if not (0.0 < rho_fraction < 1.0):
            raise ValueError(
                "rho_fraction must satisfy 0 < rho_fraction < 1 "
                f"(got {rho_fraction!r}); both sides of the split must be "
                "genuine. Use 0.999 / 0.001 to approach the boundary."
            )

        kappa_S = (1.0 - rho_fraction) * shell.delta_S
        rho_S = rho_fraction * shell.delta_S

        # Recipe defaults match scripts/run_3species_pipeline.py exactly.
        if delta_R is None:
            delta_R = 0.5 * (shell.delta_S + shell.delta_D)
        if beta_SR is None:
            beta_SR = 2.0 * shell.beta
        if beta_RD is None:
            beta_RD = 3.0 * shell.beta

        gamma = shell.gamma * float(gamma_multiplier)

        notes = (
            f"split-decay from {shell.shell_name} "
            f"(rho_fraction={rho_fraction:g}, gamma_mult={gamma_multiplier:g}, "
            f"eta=({eta_SD:g}, {eta_SR:g}, {eta_RD:g}))"
        )

        return cls(
            shell_name=shell.shell_name,
            altitude_km=shell.altitude_km,
            L=shell.L,
            kappa_S=kappa_S,
            rho_S=rho_S,
            delta_R=delta_R,
            delta_D=shell.delta_D,
            beta_SD=shell.beta,
            beta_SR=beta_SR,
            beta_RD=beta_RD,
            gamma=gamma,
            eta_SD=eta_SD,
            eta_SR=eta_SR,
            eta_RD=eta_RD,
            L_sweep_min=shell.L_sweep_min,
            L_sweep_max=shell.L_sweep_max,
            notes=notes,
        )

    def conservation_residual(self, base_delta_S: float) -> float:
        """Return ``|kappa_S + rho_S - base_delta_S|`` for diagnostic logging.

        The constraint that ``kappa_S + rho_S`` equals the original shell's
        ``delta_S`` is the comparability condition for the experiment. This
        helper reports the residual so the sweep driver can sanity-check its
        cells.
        """
        return abs(self.kappa_S + self.rho_S - base_delta_S)


# Sentinels used by tests and downstream code that wants to assert outflow
# preservation. Exposed at module level so callers don't have to recompute.
OUTFLOW_REL_TOL = _OUTFLOW_REL_TOL
OUTFLOW_ABS_TOL = _OUTFLOW_ABS_TOL
