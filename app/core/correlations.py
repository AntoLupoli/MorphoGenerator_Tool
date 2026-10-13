"""
Morphological correlation functions for the Morphogenerator.

Modello Globale Unificato (Bivariate Polynomial & Exact Closed Analytical Propagation):
Source: txt_to_image/output/correlation_ext_int_report.md

Bivariate polynomial basis:
    Y(Q, N) = ∑_{i=0}^3 ∑_{j=0}^3 c_{ij} · Q^i · N^j

Nozzle / Channel Geometry Reference:
    - Raggio canale (R):     1.0 mm
    - Diametro nozzle (D):    2.0 mm (D = 2 · R)
    - Circonferenza ref:      2πR = 6.283185307179586 mm

Fitted Primitive Models (R² > 0.99):
    - P_int(Q, N) : Internal Petal Perimeter [mm]
    - P_ext(Q, N) : External Petal Perimeter [mm]
    - Area(Q, N)  : Total Petal Area [mm²]

Analytically Propagated Quantities (Exact Closure, 0 additional free parameters):
    - P_tot(Q, N)   = P_int(Q, N) + P_ext(Q, N)
    - DSI_int(Q, N) = (N · P_int(Q, N)) / (2πR)
    - DSI_ext(Q, N) = (N · P_ext(Q, N)) / (2πR)
    - DSI_tot(Q, N) = DSI_int + DSI_ext = (N · P_tot(Q, N)) / (2πR)

Supported discrete nozzle counts: N ∈ {2, 3, 4, 5, 6}.
Valid Q range: [0.01, 0.99].
"""

import numpy as np

# Valid ranges & physical constants

Q_MIN = 0.01
Q_MAX = 0.99
VALID_N = [2, 3, 4, 5, 6]

# Nozzle & reference geometry:
# Channel radius R = 1.0 mm  -->  Nozzle diameter D = 2.0 mm (NOT 1.0 mm)
R_NOZZLE_MM = 1.0
D_NOZZLE_MM = 2.0 * R_NOZZLE_MM  # 2.0 mm
P_CIRC_REF_MM = 2.0 * np.pi * R_NOZZLE_MM  # 2πR ≈ 6.2831853 mm

# Polynomial degrees
DEG_Q = 3
DEG_N = 3

# Metric categories

CATEGORIES = {
    "Petal Geometry": [
        "Internal Petal Perimeter",
        "External Petal Perimeter",
        "Total Petal Area",
        "Total Petal Perimeter",
    ],
    "Boundary Morphology": [
        "DSI Internal",
        "DSI External",
        "DSI Total",
    ],
}

# Units

UNITS = {
    "Total Petal Area":         "mm²",
    "Total Petal Perimeter":    "mm",
    "DSI Total":                "",
    "Internal Petal Perimeter": "mm",
    "External Petal Perimeter": "mm",
    "DSI Internal":             "",
    "DSI External":             "",
}

# Short display names

SHORT_NAMES = {
    "Internal Petal Perimeter": "Internal Petal Perimeter",
    "External Petal Perimeter": "External Petal Perimeter",
    "Total Petal Area":         "Total Petal Area",
    "Total Petal Perimeter":    "Total Petal Perimeter",
    "DSI Internal":             "DSI Internal",
    "DSI External":             "DSI External",
    "DSI Total":                "DSI Total",
}

# Bivariate coefficient matrices c[i, j] for Q^i · N^j
# Rows correspond to Q^0, Q^1, Q^2, Q^3 (i in 0..3)
# Columns correspond to N^0, N^1, N^2, N^3 (j in 0..3)

BIVARIATE_COEFFICIENTS = {
    # Internal Petal Perimeter [P_int] (Fitted Primitive, R² = 0.990188)
    "Internal Petal Perimeter": np.array([
        # N^0        N^1        N^2        N^3
        [+7.866852, -2.735747, +0.521865, -0.035625],  # Q^0
        [-13.317776, +17.640566, -4.266650, +0.319224],  # Q^1
        [+48.946664, -46.706660, +11.046280, -0.822900],  # Q^2
        [-33.605749, +29.320843, -6.939346, +0.519482],  # Q^3
    ], dtype=float),

    # External Petal Perimeter [P_ext] (Fitted Primitive, R² = 0.997497)
    "External Petal Perimeter": np.array([
        # N^0        N^1        N^2        N^3
        [+0.713966, -0.558472, +0.152451, -0.012643],  # Q^0
        [+3.152727, +1.081345, -0.503050, +0.043394],  # Q^1
        [+6.059566, -8.865982, +2.128465, -0.142183],  # Q^2
        [-7.445607, +7.616842, -1.633423, +0.099934],  # Q^3
    ], dtype=float),

    # Total Petal Area [Area] (Fitted Primitive, R² = 0.998848)
    "Total Petal Area": np.array([
        # N^0        N^1        N^2        N^3
        [-0.505345, +0.389555, -0.090306, +0.006574],  # Q^0
        [+6.888808, -3.827875, +0.788832, -0.054647],  # Q^1
        [-6.993354, +4.244121, -0.877961, +0.060303],  # Q^2
        [+4.236151, -2.311432, +0.442289, -0.028690],  # Q^3
    ], dtype=float),
}

# Analytically Propagated: Total Petal Perimeter P_tot = P_int + P_ext (R² = 0.994953)
BIVARIATE_COEFFICIENTS["Total Petal Perimeter"] = (
    BIVARIATE_COEFFICIENTS["Internal Petal Perimeter"] +
    BIVARIATE_COEFFICIENTS["External Petal Perimeter"]
)


def get_cubic_coefficients(metric: str, N: int) -> list:
    """Return cubic polynomial coefficients [a₃, a₂, a₁, a₀] for Y(Q) at fixed N.

    For fixed N, the bivariate model reduces exactly to:
        Y(Q) = a₃·Q³ + a₂·Q² + a₁·Q + a₀
    where a_i = ∑_{j=0}^3 c_{ij} · N^j.
    For DSI metrics, the coefficients are scaled by N / (2πR).
    """
    n_vec = np.array([1.0, float(N), float(N)**2, float(N)**3], dtype=float)

    if metric in BIVARIATE_COEFFICIENTS:
        C = BIVARIATE_COEFFICIENTS[metric]
        a = C @ n_vec  # [a0, a1, a2, a3]
        return [float(a[3]), float(a[2]), float(a[1]), float(a[0])]

    if metric == "DSI Internal":
        a_int = get_cubic_coefficients("Internal Petal Perimeter", N)
        factor = float(N) / P_CIRC_REF_MM
        return [factor * c for c in a_int]

    if metric == "DSI External":
        a_ext = get_cubic_coefficients("External Petal Perimeter", N)
        factor = float(N) / P_CIRC_REF_MM
        return [factor * c for c in a_ext]

    if metric == "DSI Total":
        a_tot = get_cubic_coefficients("Total Petal Perimeter", N)
        factor = float(N) / P_CIRC_REF_MM
        return [factor * c for c in a_tot]

    raise ValueError(f"Unknown metric: '{metric}'")


# Precomputed cubic polynomial coefficients dictionary: {metric: {N: [a₃, a₂, a₁, a₀]}}
# Preserved for full backwards-compatibility with solver.py and statistics.py
COEFFICIENTS = {
    metric: {
        n: get_cubic_coefficients(metric, n) for n in VALID_N
    }
    for metric in [
        "Internal Petal Perimeter",
        "External Petal Perimeter",
        "Total Petal Area",
        "Total Petal Perimeter",
        "DSI Internal",
        "DSI External",
        "DSI Total",
    ]
}


# Public API

def validate_Q(Q: float) -> None:
    """Raise ValueError if Q is outside the valid range."""
    if Q < Q_MIN or Q > Q_MAX:
        raise ValueError(
            f"Q = {Q} is out of valid range [{Q_MIN}, {Q_MAX}]. "
            "Value not available."
        )


def validate_N(metric: str, N: int) -> None:
    """Raise ValueError if N is not available for the given metric."""
    available = get_available_N(metric)
    if N not in available:
        raise ValueError(
            f"N = {N} is not available for metric '{metric}'. "
            f"Valid values: {available}"
        )


def evaluate(metric: str, N: int, Q: float) -> float:
    """Evaluate the correlation for given metric, N, and Q.

    Returns the scalar output value Y(Q, N).
    """
    validate_Q(Q)
    validate_N(metric, N)
    a3, a2, a1, a0 = COEFFICIENTS[metric][N]
    return a3 * Q**3 + a2 * Q**2 + a1 * Q + a0


def evaluate_range(metric: str, N: int, Q_array) -> np.ndarray:
    """Evaluate the correlation for an array of Q values at fixed N (vectorised)."""
    Q_arr = np.asarray(Q_array, dtype=float)
    a3, a2, a1, a0 = COEFFICIENTS[metric][N]
    return a3 * Q_arr**3 + a2 * Q_arr**2 + a1 * Q_arr + a0


def evaluate_bivariate(metric: str, Q, N) -> np.ndarray:
    """Direct bivariate evaluation for arbitrary Q and N (scalar or array)."""
    Q_arr = np.asarray(Q, dtype=float)
    N_arr = np.asarray(N, dtype=float)

    def _eval_matrix(C: np.ndarray, q, n):
        res = np.zeros_like(q * n, dtype=float)
        for i in range(DEG_Q + 1):
            for j in range(DEG_N + 1):
                res = res + C[i, j] * (q**i) * (n**j)
        return res

    if metric in BIVARIATE_COEFFICIENTS:
        return _eval_matrix(BIVARIATE_COEFFICIENTS[metric], Q_arr, N_arr)
    if metric == "DSI Internal":
        p_int = evaluate_bivariate("Internal Petal Perimeter", Q_arr, N_arr)
        return (N_arr * p_int) / P_CIRC_REF_MM
    if metric == "DSI External":
        p_ext = evaluate_bivariate("External Petal Perimeter", Q_arr, N_arr)
        return (N_arr * p_ext) / P_CIRC_REF_MM
    if metric == "DSI Total":
        p_tot = evaluate_bivariate("Total Petal Perimeter", Q_arr, N_arr)
        return (N_arr * p_tot) / P_CIRC_REF_MM

    raise ValueError(f"Unknown metric: '{metric}'")


def get_available_N(metric: str) -> list:
    """Return sorted list of available N values for a metric."""
    return sorted(COEFFICIENTS.get(metric, {}).keys())


def get_all_metrics() -> list:
    """Return list of all available metric names."""
    return list(COEFFICIENTS.keys())


def get_unit(metric: str) -> str:
    """Return unit string for a metric."""
    return UNITS.get(metric, "")


def get_short_name(metric: str) -> str:
    """Return short display name for a metric."""
    return SHORT_NAMES.get(metric, metric)


def get_category(metric: str) -> str:
    """Return the category a metric belongs to."""
    for cat, metrics in CATEGORIES.items():
        if metric in metrics:
            return cat
    return "Other"
