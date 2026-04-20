"""Jacobian and eigenvalue tracking for the Kessler ODE (Task 4).

The Jacobian at a fixed point ``(S*, D*)`` is taken verbatim from the PDF /
CLAUDE.md::

    J = [[-delta_S - beta * D*,   -beta * S*                   ],
         [ beta * D*,              beta * S* + 2 * gamma * D* - delta_D]]

Eigenvalues are computed with :func:`numpy.linalg.eigvals`.

``eigenvalue_pair`` returns a ``(alpha, omega)`` tuple:

* When the eigenvalues are a complex conjugate pair, ``alpha`` is their shared
  real part and ``omega`` is the absolute value of their imaginary part.
* When the eigenvalues are real (no rotation — and therefore no Hopf
  possible), ``alpha`` is the larger of the two real parts (the component
  that governs stability) and ``omega`` is zero.

Both modules downstream (``hopf_detector``, ``early_warning``) treat
``omega > 0`` as the signal that the fixed point is a spiral and therefore a
candidate site for a Hopf bifurcation.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .shell_config import ShellConfig

__all__ = ["jacobian", "eigenvalue_pair", "track_eigenvalues"]


# A generous floor for treating a numpy-computed imaginary part as
# numerically zero. We scale it by the magnitude of the eigenvalues so that
# large-trace Jacobians (like the ones produced at high D*) do not get their
# complex pairs misclassified as real.
_OMEGA_REL_TOL = 1e-10
_OMEGA_ABS_TOL = 1e-12


def jacobian(S_star: float, D_star: float, params: ShellConfig) -> np.ndarray:
    """Return the 2x2 Jacobian of the ODE at the fixed point ``(S*, D*)``.

    The Jacobian is derived analytically from the ODE in
    :mod:`bifurcation_engine.src.model`; see module docstring for the exact
    form. Only ``params.delta_S``, ``params.delta_D``, ``params.beta`` and
    ``params.gamma`` are read; ``params.L`` is not used (it enters the
    dynamics only through the fixed-point location, not through the
    Jacobian).
    """
    j00 = -params.delta_S - params.beta * D_star
    j01 = -params.beta * S_star
    j10 = params.beta * D_star
    j11 = params.beta * S_star + 2.0 * params.gamma * D_star - params.delta_D
    return np.array([[j00, j01], [j10, j11]], dtype=float)


def eigenvalue_pair(
    S_star: float,
    D_star: float,
    params: ShellConfig,
) -> tuple[float, float]:
    """Return ``(alpha, omega)`` for the eigenvalues of the Jacobian at
    ``(S*, D*)``.

    See module docstring for the convention used when the eigenvalues are
    real.
    """
    J = jacobian(S_star, D_star, params)
    eigs = np.linalg.eigvals(J)

    # For a real 2x2 matrix eigvals always returns a complex-conjugate pair
    # (possibly with zero imaginary parts when both roots are real).
    im_magnitude = float(max(abs(eigs[0].imag), abs(eigs[1].imag)))
    re_magnitude = float(max(abs(eigs[0].real), abs(eigs[1].real)))
    threshold = max(_OMEGA_ABS_TOL, _OMEGA_REL_TOL * re_magnitude)

    if im_magnitude > threshold:
        # Complex conjugate pair: both eigenvalues share a real part.
        alpha = 0.5 * (float(eigs[0].real) + float(eigs[1].real))
        omega = im_magnitude
        return alpha, omega

    # Real eigenvalues: stability is governed by the larger real part, and
    # there is no rotation so omega is exactly zero.
    alpha = float(max(eigs[0].real, eigs[1].real))
    return alpha, 0.0


def track_eigenvalues(
    continuation_result: Mapping[str, np.ndarray],
    params: ShellConfig,
) -> dict[str, np.ndarray]:
    """Evaluate ``(alpha, omega)`` at every fixed point in a sweep.

    Parameters
    ----------
    continuation_result:
        A dict with the shape produced by
        :func:`bifurcation_engine.src.fixed_points.continuation_sweep`;
        specifically, keys ``L``, ``S_star``, ``D_star`` (all 1-D arrays of
        equal length, optionally also ``branch``).
    params:
        Shell parameters. Only the non-``L`` fields are read — the Jacobian
        does not depend on the launch rate directly.

    Returns
    -------
    dict
        A dict with keys ``L``, ``alpha``, ``omega``, ``is_complex`` (bool
        array flagging entries where ``omega > 0``). When the input contains
        a ``branch`` column, it is copied through unchanged so callers can
        filter by branch before feeding the result into the Hopf detector.
    """
    L = np.asarray(continuation_result["L"], dtype=float)
    S = np.asarray(continuation_result["S_star"], dtype=float)
    D = np.asarray(continuation_result["D_star"], dtype=float)
    if not (L.shape == S.shape == D.shape):
        raise ValueError(
            "continuation_result arrays must all have the same shape"
        )

    n = L.size
    alpha = np.zeros(n, dtype=float)
    omega = np.zeros(n, dtype=float)

    for i in range(n):
        alpha[i], omega[i] = eigenvalue_pair(float(S[i]), float(D[i]), params)

    is_complex = omega > 0.0

    out: dict[str, np.ndarray] = {
        "L": L,
        "alpha": alpha,
        "omega": omega,
        "is_complex": is_complex,
    }
    if "branch" in continuation_result:
        out["branch"] = np.asarray(continuation_result["branch"])
    return out
