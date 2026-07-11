"""
ai/risk_meter.py
------------------
Shared risk-level classification used by the disease, pest, weather,
and priority-engine modules. Wraps Config.RISK_THRESHOLDS / RISK_COLORS
so every module labels risk consistently (Low / Medium / High /
Critical) instead of each one inventing its own bands.
"""

from config import Config


def get_risk_level(score):
    """
    Maps a 0-100 risk/severity score onto Config.RISK_THRESHOLDS.
    Bands are checked in order (Low -> Critical); the first band whose
    upper bound is >= score wins, so a score of exactly 25 falls in
    "low" rather than "medium".

    Returns "Low", "Medium", "High", or "Critical".
    """
    score = max(0, min(100, score))
    for label, (_, high) in Config.RISK_THRESHOLDS.items():
        if score <= high:
            return label.capitalize()
    return "Critical"


def get_risk_color(risk_level):
    """Returns the hex color configured for a given risk level label."""
    return Config.RISK_COLORS.get(risk_level, "#757575")


def build_risk_meter(score):
    """
    Convenience wrapper returning everything a template needs to render
    the Risk Meter widget in one call: the numeric score, its label,
    and the color to display.
    """
    score = round(max(0, min(100, score)), 1)
    level = get_risk_level(score)
    return {
        "score": score,
        "level": level,
        "color": get_risk_color(level),
    }