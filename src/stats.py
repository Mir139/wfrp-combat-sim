"""Small statistics helpers."""
from math import sqrt
from statistics import NormalDist

DEFAULT_CONFIDENCE = 0.95


def wilson_interval(successes, total, confidence=DEFAULT_CONFIDENCE):
    """Wilson score interval for a proportion; (0, 1) when there is no data."""
    if total == 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(centre - half, 0.0), min(centre + half, 1.0))
