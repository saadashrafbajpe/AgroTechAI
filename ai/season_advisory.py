"""
ai/season_advisory.py
------------------------
Season Advisory module. A pure lookup against crop_data/<crop>.json's
seasonal_calendar for the current (or a specified) month - no scoring
or computation needed, just structured retrieval of the offline
agricultural knowledge base.
"""

from ai.crop_health import get_current_season


def get_season_advisory(crop_key, month=None):
    """
    Main entry point, intended to be called by routes/dashboard.py (or
    a dedicated season route) whenever the farmer views seasonal
    guidance for their crop.

    Returns a dict with: season, months, operations, precautions
    """
    entry = get_current_season(crop_key, month)

    if entry is None:
        return {"season": None, "months": None, "operations": [], "precautions": []}

    return {
        "season": entry["season"],
        "months": entry["months"],
        "operations": entry.get("operations", []),
        "precautions": entry.get("precautions", []),
    }