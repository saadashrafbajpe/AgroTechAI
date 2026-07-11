"""
ai/weather_predictor.py
--------------------------
Offline Weather Risk Predictor. The farmer answers 5 simple questions
about current local conditions (rainfall, cloud cover, wind,
temperature, humidity) instead of relying on an internet weather
service, and the module matches those answers against the crop's
weather_sensitivity.risk_conditions from crop_data/<crop>.json.

ASSUMED FORM FIELDS (routes/weather.py wasn't available when this was
written) - update WEATHER_FIELDS/the expected values below if your
actual questionnaire differs:
    rainfall:    "none" | "light" | "moderate" | "heavy"
    cloud_cover: "clear" | "partly_cloudy" | "overcast"
    wind:        "calm" | "breezy" | "strong" | "hot_dry"
    temperature: "low" | "normal" | "high"
    humidity:    "low" | "normal" | "high"
"""

from ai.crop_health import load_crop_data
from ai.risk_meter import build_risk_meter

# Keep in sync with the form fields collected in routes/weather.py
WEATHER_FIELDS = ["rainfall", "cloud_cover", "wind", "temperature", "humidity"]


def _condition_fully_matches(answers, triggers):
    """
    A risk_condition's `triggers` dict only lists the 1-2 fields that
    actually matter for it (e.g. {"rainfall": "heavy"}). Requires every
    listed trigger field to match - a partial match on a 1-2 field
    trigger isn't meaningful evidence of that specific risk.
    """
    if not triggers:
        return False
    return all(answers.get(field) == expected for field, expected in triggers.items())


def predict_weather_risk(crop_key, answers):
    """
    Main entry point, intended to be called by routes/weather.py.

    Returns a dict with:
        weather_risk_score, risk_level, risk_meter, dominant_risk,
        impact, matched_conditions
    """
    data = load_crop_data(crop_key)
    risk_conditions = data.get("weather_sensitivity", {}).get("risk_conditions", [])

    matched_conditions = [
        c for c in risk_conditions if _condition_fully_matches(answers, c.get("triggers", {}))
    ]

    if not matched_conditions:
        risk = build_risk_meter(5)
        return {
            "weather_risk_score": 5.0,
            "risk_level": risk["level"],
            "risk_meter": risk,
            "dominant_risk": "No significant weather risk detected",
            "impact": None,
            "matched_conditions": [],
        }

    # The dominant risk is whichever matched condition carries the
    # highest severity_weight - that's the one the farmer should act on
    # first if several conditions matched simultaneously.
    dominant = max(matched_conditions, key=lambda c: c.get("severity_weight", 0))
    risk = build_risk_meter(dominant.get("severity_weight", 30))

    return {
        "weather_risk_score": risk["score"],
        "risk_level": risk["level"],
        "risk_meter": risk,
        "dominant_risk": dominant["condition"],
        "impact": dominant.get("impact"),
        "matched_conditions": [c["condition"] for c in matched_conditions],
    }