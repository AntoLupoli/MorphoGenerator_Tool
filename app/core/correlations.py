"""
Morphological correlation functions for the Morphogenerator.

Every curve is a cubic polynomial of the form:
    Y(Q) = a₃·Q³ + a₂·Q² + a₁·Q + a₀

The coefficients were obtained by fitting experimental data from COMSOL
simulations. Only N ∈ {2, 3, 4, 5, 6} are supported.

The valid Q range is [0.01, 0.99]. Values outside this range are rejected.
"""

import numpy as np

# Valid ranges

Q_MIN = 0.01
Q_MAX = 0.99
VALID_N = [2, 3, 4, 5, 6]

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

# Polynomial coefficients: {metric: {N: [a₃, a₂, a₁, a₀]}}

COEFFICIENTS = {
    "Internal Petal Perimeter": {
        2: [  1.480436,  -6.949856,  7.501355,  4.198959],
        3: [  5.418526, -13.241744,  9.525170,  3.394150],
        4: [  6.171101, -14.315808,  9.713269,  3.000551],
        5: [  4.400335, -11.151966,  7.966273,  2.798599],
        6: [  4.757035, -11.458686,  7.929430,  2.545620],
    },
    "External Petal Perimeter": {
        2: [ 2.030400, -4.274735,  3.647762,  0.104651],
        3: [ 3.822241, -5.699046,  3.146092,  0.069136],
        4: [ 3.142030, -4.321027,  2.190873,  0.103954],
        5: [ 2.388670, -2.916607,  1.417846,  0.156555],
        6: [ 1.014582, -1.201776,  0.901441,  0.119362],
    },
    "Total Petal Area": {
        2: [ 1.176846, -1.573230,  1.970099, -0.036567],
        3: [ 0.412140, -0.379643,  0.953667,  0.034825],
        4: [ 0.374425, -0.437032,  0.814555,  0.018516],
        5: [ 0.086312, -0.081790,  0.584219,  0.014289],
        6: [ 0.116865, -0.148378,  0.534730, -0.000845],
    },
    "Total Petal Perimeter": {
        2: [  3.510836, -11.224591, 11.149116,  4.303610],
        3: [  9.240767, -18.940790, 12.671262,  3.463286],
        4: [  9.313131, -18.636835, 11.904143,  3.104505],
        5: [  6.789005, -14.068573,  9.384119,  2.955154],
        6: [  5.771617, -12.660463,  8.830871,  2.664982],
    },
    "DSI Internal": {
        2: [ 0.942953,  -4.426660,  4.777933,  2.674496],
        3: [ 5.176935, -12.651348,  9.100481,  3.242819],
        4: [ 7.861275, -18.236699, 12.373592,  3.822358],
        5: [ 7.006902, -17.757907, 12.685149,  4.456368],
        6: [ 9.089875, -21.895579, 15.151776,  4.864243],
    },
    "DSI External": {
        2: [ 1.293248, -2.722761,  2.323415,  0.066657],
        3: [ 3.651823, -5.444949,  3.005820,  0.066053],
        4: [ 4.002586, -5.504493,  2.790921,  0.132426],
        5: [ 3.803615, -4.644278,  2.257716,  0.249291],
        6: [ 1.938692, -2.296388,  1.722499,  0.228080],
    },
    "DSI Total": {
        2: [  2.236201,  -7.149421,  7.101348,  2.741153],
        3: [  8.828758, -18.096297, 12.106301,  3.308872],
        4: [ 11.863862, -23.741192, 15.164513,  3.954784],
        5: [ 10.810517, -22.402186, 14.942865,  4.705659],
        6: [ 11.028568, -24.191967, 16.874275,  5.092323],
    },
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
    """Evaluate the polynomial correlation for given metric, N, and Q.

    Returns the scalar output value Y(Q).
    """
    validate_Q(Q)
    validate_N(metric, N)
    a3, a2, a1, a0 = COEFFICIENTS[metric][N]
    return a3 * Q**3 + a2 * Q**2 + a1 * Q + a0


def evaluate_range(metric: str, N: int, Q_array) -> np.ndarray:
    """Evaluate the polynomial for an array of Q values (vectorised)."""
    Q_arr = np.asarray(Q_array, dtype=float)
    a3, a2, a1, a0 = COEFFICIENTS[metric][N]
    return a3 * Q_arr**3 + a2 * Q_arr**2 + a1 * Q_arr + a0


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
