"""
utils/calculations.py
----------------------
Small, dependency-free numeric helpers shared by the ai/ decision-support
modules (disease_detector, pest_predictor, weather_predictor, growth_stage,
crop_health). Kept separate from the modules themselves so the scoring
math can be tested and reused without pulling in Flask or SQLite.
"""


def clamp(value, low=0, high=100):
    """Constrain a value to [low, high]."""
    return max(low, min(high, value))


def weighted_average(components):
    """
    components: dict of {name: (value, weight)}
    Returns the weighted average of the values, rounded to 1 decimal.
    Weights do not need to sum to 1 — they are normalized here.

    Example:
        weighted_average({
            "disease": (80, 0.5),
            "pest": (60, 0.3),
            "weather": (90, 0.2),
        })
    """
    if not components:
        return 0.0
    total_weight = sum(weight for _, weight in components.values())
    if total_weight == 0:
        return 0.0
    total = sum(value * weight for value, weight in components.values())
    return round(total / total_weight, 1)


def normalize(value, in_min, in_max, out_min=0, out_max=100):
    """Rescale value from [in_min, in_max] into [out_min, out_max]."""
    if in_max == in_min:
        return out_min
    ratio = (value - in_min) / (in_max - in_min)
    return round(out_min + ratio * (out_max - out_min), 1)


def percentage(part, whole):
    """Safe percentage calculation; returns 0.0 if whole is 0."""
    if not whole:
        return 0.0
    return round((part / whole) * 100, 1)


def score_to_band(score, bands, default=None):
    """
    Maps a numeric score onto a list of band dicts, each shaped like
    {"min": int, "max": int, ...}. Returns the first matching band,
    or `default` (or the last band) if nothing matches.

    Used by ai/growth_stage.py to map a maturity score onto a crop's
    growth-stage bands, and by ai/risk_meter.py to map a risk score
    onto Low/Medium/High/Critical bands.
    """
    for band in bands:
        if band["min"] <= score <= band["max"]:
            return band
    return default if default is not None else (bands[-1] if bands else None)


def combine_binary_flags(flags, weight_each):
    """
    Sums a fixed weight for every True/'yes' flag in an iterable —
    a common pattern in the pest and disease questionnaires where
    several yes/no answers each add a fixed amount of risk.
    """
    count = sum(1 for f in flags if f in (True, "yes", "high"))
    return clamp(count * weight_each)