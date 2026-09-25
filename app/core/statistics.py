"""
Statistical analysis utilities for the Morphogenerator.

Provides sensitivity analysis (∂Y/∂Q) and cross-N comparison.
"""

import numpy as np
from . import correlations


# Sensitivity (first derivative)

def sensitivity(metric: str, N: int, Q: float) -> float:
    """Compute dY/dQ at a specific Q for given (metric, N).

    The derivative of Y = a₃Q³ + a₂Q² + a₁Q + a₀ is:
        dY/dQ = 3a₃Q² + 2a₂Q + a₁
    """
    correlations.validate_N(metric, N)
    a3, a2, a1, _ = correlations.COEFFICIENTS[metric][N]
    return 3 * a3 * Q**2 + 2 * a2 * Q + a1


def sensitivity_range(metric: str, N: int, Q_array) -> np.ndarray:
    """Vectorised dY/dQ over an array of Q values."""
    Q_arr = np.asarray(Q_array, dtype=float)
    a3, a2, a1, _ = correlations.COEFFICIENTS[metric][N]
    return 3 * a3 * Q_arr**2 + 2 * a2 * Q_arr + a1


# Cross‑N comparison

def cross_N_comparison(
    metric: str,
    Q: float,
    N_values: list = None,
) -> dict:
    """Compare a metric's value and sensitivity across different N at a fixed Q.

    Returns
    -------
    dict : {N: {"value": float, "sensitivity": float, "unit": str}}
    """
    if N_values is None:
        N_values = correlations.get_available_N(metric)

    results = {}
    for N in N_values:
        results[N] = {
            "value":       round(correlations.evaluate(metric, N, Q), 6),
            "sensitivity": round(sensitivity(metric, N, Q), 6),
            "unit":        correlations.get_unit(metric),
        }
    return results


def metric_range(metric: str, N: int) -> dict:
    """Compute the min/max of a metric over the valid Q range for a given N.

    Useful for understanding the output range when setting inverse targets.
    """
    Q_arr = np.linspace(correlations.Q_MIN, correlations.Q_MAX, 2000)
    values = correlations.evaluate_range(metric, N, Q_arr)
    return {
        "min":   round(float(np.min(values)), 6),
        "max":   round(float(np.max(values)), 6),
        "Q_min": round(float(Q_arr[np.argmin(values)]), 4),
        "Q_max": round(float(Q_arr[np.argmax(values)]), 4),
    }
