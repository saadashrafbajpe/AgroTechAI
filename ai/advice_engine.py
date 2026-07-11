"""
ai/advice_engine.py
----------------------
Daily AI Advice. Generated automatically each time the app is opened -
combines the Crop Health Score, weather risk, pest risk, and season
advisory for the farmer's active session into a short, plain-language
"what to do today" headline plus the full Priority-Based Action List.

Note: disease_records/pest_records/weather_records store only the
final scores and labels (not the full treatment/management text), so
_reshape_* below re-derive a minimal summary line from what's actually
persisted. If you want the full original treatment/management lists to
carry through to the next day's advice, either re-run analyze_disease()
etc. against the stored `answers` JSON column, or extend the schema to
store the treatment list directly.
"""

from ai.crop_health import get_latest_health_score
from ai.season_advisory import get_season_advisory
from ai.priority_engine import build_priority_actions
from utils.database import get_latest_for_session, insert_advisory_log


def _health_headline(health_result):
    if not health_result:
        return "Complete a disease, pest, or weather check today to get a personalized health score."
    score = health_result["health_score"]
    if score >= 85:
        return f"Your crop is in excellent condition today (Health Score: {score}%)."
    if score >= 70:
        return f"Your crop is generally healthy (Health Score: {score}%), but a few things need attention."
    if score >= 50:
        return f"Your crop's health score is {score}% - some issues need action this week."
    return f"Your crop's health score is {score}% - please review the critical actions below right away."


def _reshape_disease(record):
    if not record:
        return None
    return {
        "detected_disease": record["detected_disease"],
        "risk_level": record["risk_level"],
        "treatment": [f"Follow up on the detected condition: {record['detected_disease']}."],
    }


def _reshape_pest(record):
    if not record:
        return None
    return {
        "predicted_pest": record["predicted_pest"],
        "risk_level": record["risk_level"],
        "management": [f"Monitor and manage: {record['predicted_pest']}."],
    }


def _reshape_weather(record):
    if not record:
        return None
    return {
        "risk_level": record["risk_level"],
        "impact": record.get("dominant_risk"),
    }


def generate_daily_advice(session_id, crop_key, month=None):
    """
    Main entry point, intended to be called once per day from
    routes/dashboard.py when the app opens.

    Returns a dict with:
        headline, health_score_result, priority_actions, season_advisory
    """
    latest = get_latest_for_session(session_id)
    health_result = get_latest_health_score(session_id)
    season = get_season_advisory(crop_key, month)

    priority_actions = build_priority_actions(
        disease_result=_reshape_disease(latest.get("disease")),
        pest_result=_reshape_pest(latest.get("pest")),
        weather_result=_reshape_weather(latest.get("weather")),
        season_advisory=season,
    )

    headline = _health_headline(health_result)

    insert_advisory_log(
        session_id=session_id,
        crop_key=crop_key,
        advice_text=headline,
        priority_actions=[a["text"] for a in priority_actions],
    )

    return {
        "headline": headline,
        "health_score_result": health_result,
        "priority_actions": priority_actions,
        "season_advisory": season,
    }