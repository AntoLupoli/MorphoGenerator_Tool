"""
Forward and inverse parameter solver for the Morphogenerator.

• Forward mode:  Given (N, Q) → compute all output metrics.
• Inverse mode:  Given (metric, target, N) → find Q that produces it
                 by solving the cubic polynomial analytically.
• Parametric sweep: Find all (Q, N) pairs whose output falls within
                    a tolerance band around a target value.
"""

import numpy as np
from . import correlations


def forward(N: int, Q: float) -> dict:
    """Compute every available metric for a given (N, Q) pair.

    Returns
    -------
    dict : {metric_name: {"value": float, "unit": str}} or
           {"error": str} if Q is out of range.
    """
    try:
        correlations.validate_Q(Q)
    except ValueError as exc:
        return {"error": str(exc)}

    results = {}
    for metric in correlations.get_all_metrics():
        avail = correlations.get_available_N(metric)
        if N in avail:
            results[metric] = {
                "value": round(correlations.evaluate(metric, N, Q), 6),
                "unit":  correlations.get_unit(metric),
            }
    return results


def inverse(metric: str, target: float, N: int) -> list:
    """Find Q values that produce *target* for a given (metric, N).

    Solves  a₃Q³ + a₂Q² + a₁Q + (a₀ − target) = 0  analytically,
    then keeps only real roots inside [Q_MIN, Q_MAX].

    Returns a sorted list of valid Q values (may be empty).
    """
    correlations.validate_N(metric, N)
    a3, a2, a1, a0 = correlations.COEFFICIENTS[metric][N]

    # Build polynomial coefficients: a3*Q^3 + a2*Q^2 + a1*Q + (a0 - target)
    poly = [a3, a2, a1, a0 - target]
    roots = np.roots(poly)

    valid = []
    for r in roots:
        if np.isreal(r):
            q = float(np.real(r))
            if correlations.Q_MIN <= q <= correlations.Q_MAX:
                valid.append(round(q, 6))

    return sorted(valid)


def parametric_sweep(
    metric: str,
    target: float,
    tolerance: float = 0.05,
    N_values: list = None,
    Q_step: float = 0.001,
) -> list:
    """Find all (Q, N) pairs whose output is within ±tolerance of *target*.

    The sweep evaluates the polynomial densely over Q ∈ [Q_MIN, Q_MAX]
    for each requested N, collecting every match.

    Parameters
    ----------
    metric : str
        The output metric to match.
    target : float
        Desired output value.
    tolerance : float, optional
        Acceptable absolute error (default 0.05).
    N_values : list[int], optional
        Which N values to sweep; defaults to all available.
    Q_step : float, optional
        Resolution of the Q scan (default 0.001).

    Returns
    -------
    list[dict] : Each dict has keys "N", "Q", "value", "error".
                 Sorted by ascending absolute error.
    """
    if N_values is None:
        N_values = correlations.get_available_N(metric)

    Q_range = np.arange(
        correlations.Q_MIN,
        correlations.Q_MAX + Q_step / 2,
        Q_step,
    )

    results = []
    for N in N_values:
        if N not in correlations.get_available_N(metric):
            continue
        values = correlations.evaluate_range(metric, N, Q_range)
        errors = np.abs(values - target)
        mask = errors <= tolerance

        if np.any(mask):
            best_idx = np.argmin(errors[mask])
            q = Q_range[mask][best_idx]
            v = values[mask][best_idx]
            e = errors[mask][best_idx]
            
            results.append({
                "N":     int(N),
                "Q":     round(float(q), 4),
                "value": round(float(v), 6),
                "error": round(float(e), 6),
            })

    results.sort(key=lambda x: x["error"])
    return results


def forward_sweep(
    N: int,
    metric: str,
    Q_start: float = None,
    Q_end: float = None,
    Q_step: float = 0.01,
) -> list:
    """Evaluate a single metric across a Q range for a fixed N.

    Returns a list of {"Q": float, "value": float} dicts.
    """
    if Q_start is None:
        Q_start = correlations.Q_MIN
    if Q_end is None:
        Q_end = correlations.Q_MAX

    Q_range = np.arange(Q_start, Q_end + Q_step / 2, Q_step)
    values = correlations.evaluate_range(metric, N, Q_range)

    return [
        {"Q": round(float(q), 4), "value": round(float(v), 6)}
        for q, v in zip(Q_range, values)
    ]
