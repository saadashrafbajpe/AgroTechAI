"""
ai/crop_health.py
--------------------
Two responsibilities that every other ai/ module depends on, so they
live in one place instead of being duplicated:

1. load_crop_data() - the single reader of crop_data/<crop>.json,
   cached since the file never changes at runtime and is read on
   nearly every request.
2. compute_crop_health_score() - combines the disease/pest/weather
   component scores into the single Crop Health Score percentage
   shown on the dashboard, using Config.HEALTH_SCORE_WEIGHTS.
"""

import json
import os
import datetime
from functools import lru_cache

from config import Config
from utils.calculations import weighted_average
from ai.risk_meter import build_risk_meter

_MONTH_NAMES = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december",
}


@lru_cache(maxsize=None)
def load_crop_data(crop_key):
    """
    Loads and caches crop_data/<crop_key>.json. All other ai/ modules
    should read crop knowledge through this function rather than
    opening the file themselves, so there is exactly one place that
    knows the on-disk path and does the JSON parsing.
    """
    path = os.path.join(Config.CROP_DATA_DIR, f"{crop_key}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No crop data file found for '{crop_key}' at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_season(crop_key, month=None):
    """
    Resolves which seasonal_calendar entry covers the given month
    (1-12, defaults to the current month) for this crop. Matching is
    done by checking whether the month name appears in that entry's
    free-text "months" field (e.g. "June-September").
    """
    month = month or datetime.date.today().month
    target = _MONTH_NAMES[month]

    data = load_crop_data(crop_key)
    calendar = data.get("seasonal_calendar", [])
    for entry in calendar:
        if target in entry["months"].lower():
            return entry
    return calendar[0] if calendar else None


def compute_crop_health_score(disease_score=None, pest_score=None, weather_score=None):
    """
    Combines up to three component scores (each 0-100, where 100 =
    perfectly healthy / no risk) into a single Crop Health Score using
    Config.HEALTH_SCORE_WEIGHTS. Any component the caller doesn't have
    yet (e.g. the farmer hasn't run that check today) is simply left
    out of the weighted average rather than assumed to be healthy.
    """
    components = {}
    if disease_score is not None:
        components["disease"] = (disease_score, Config.HEALTH_SCORE_WEIGHTS["disease"])
    if pest_score is not None:
        components["pest"] = (pest_score, Config.HEALTH_SCORE_WEIGHTS["pest"])
    if weather_score is not None:
        components["weather"] = (weather_score, Config.HEALTH_SCORE_WEIGHTS["weather"])

    if not components:
        return None

    score = weighted_average(components)
    return {
        "health_score": score,
        # Health and risk are inverses of each other on the same 0-100
        # scale, so the Risk Meter shown alongside the Health Score
        # reflects (100 - health_score).
        "risk_meter": build_risk_meter(100 - score),
        "components_used": list(components.keys()),
    }


def get_latest_health_score(session_id):
    """
    Pulls the latest disease/pest/weather records for a session from
    SQLite and computes today's Crop Health Score from whichever
    modules the farmer has actually completed so far.

    Note: disease_records stores health_score directly (100 = healthy),
    while pest_records/weather_records store *_risk_score (100 = worst
    case) - these are inverted here so all three combine on the same
    "higher is healthier" scale.
    """
    from utils.database import get_latest_for_session

    latest = get_latest_for_session(session_id)

    disease_score = latest["disease"]["health_score"] if latest.get("disease") else None
    pest_score = (100 - latest["pest"]["pest_risk_score"]) if latest.get("pest") else None
    weather_score = (100 - latest["weather"]["weather_risk_score"]) if latest.get("weather") else None

    return compute_crop_health_score(disease_score, pest_score, weather_score)