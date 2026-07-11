"""
ai/priority_engine.py
------------------------
Priority-Based Action List. Takes the outputs of the disease, pest,
weather, and season-advisory modules and merges them into one
urgency-ordered, color-coded action list, so the farmer sees the most
critical thing to do today first and can visually distinguish it from
lower-priority tasks.
"""

from config import Config

# Urgency rank used for sorting - lower number sorts first (most urgent)
_URGENCY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _actions_from(source_label, risk_level, items):
    """Wraps a list of treatment/management/precaution strings from one
    module into individual color-coded action entries."""
    color = Config.RISK_COLORS.get(risk_level, "#757575")
    rank = _URGENCY_ORDER.get(risk_level, 3)
    return [
        {"text": item, "source": source_label, "risk_level": risk_level, "color": color, "urgency_rank": rank}
        for item in items
    ]


def build_priority_actions(disease_result=None, pest_result=None,
                            weather_result=None, season_advisory=None):
    """
    Combines whichever module results are available (any can be None if
    the farmer hasn't run that check yet today) into a single flat,
    urgency-sorted action list ready for a priority-list template.
    """
    actions = []

    if disease_result and disease_result.get("detected_disease") not in (None, "No disease detected"):
        actions += _actions_from("Disease", disease_result["risk_level"], disease_result.get("treatment", []))

    if pest_result and pest_result.get("predicted_pest") not in (None, "No significant pest risk detected"):
        actions += _actions_from("Pest", pest_result["risk_level"], pest_result.get("management", []))

    if weather_result and weather_result.get("impact"):
        actions += _actions_from("Weather", weather_result["risk_level"], [weather_result["impact"]])

    if season_advisory and season_advisory.get("operations"):
        # Seasonal operations are routine, not urgent - always "Low" so
        # they naturally sort beneath any active disease/pest/weather issue.
        actions += _actions_from("Season", "Low", season_advisory["operations"])

    actions.sort(key=lambda a: a["urgency_rank"])
    return actions