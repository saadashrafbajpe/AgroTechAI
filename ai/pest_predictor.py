"""
ai/pest_predictor.py
-----------------------
Pest Risk Predictor. Estimates the likelihood of pest infestation
using the farmer's observations, the crop's current season (derived
from today's date via crop_data seasonal_calendar), and optional image
input. Matches against crop_data/<crop>.json -> "pests".

ASSUMED FORM FIELDS (routes/pest.py wasn't available when this was
written) - update PEST_FIELDS/the expected values below if your actual
questionnaire differs:
    pest_sightings:    "none" | "few" | "many"
    affected_part:     "leaves" | "stem_trunk" | "roots" | "crown_bud" | "fruit_nut"
    crop_stage:        "young" | "mature" | "flowering" | "fruiting"
    recent_weather:    "dry" | "humid" | "rainy"
    nearby_vegetation: "weeds_present" | "clean"
"""

from ai.crop_health import load_crop_data, get_current_season
from ai.risk_meter import build_risk_meter
from utils.calculations import clamp

# Keep in sync with the form fields collected in routes/pest.py
PEST_FIELDS = ["pest_sightings", "affected_part", "crop_stage", "recent_weather", "nearby_vegetation"]

SIGHTING_WEIGHT = {"none": 0, "few": 30, "many": 60}


def _season_key_of(data, season_entry):
    """Recovers the season's short key (e.g. "monsoon") from the full
    seasonal_calendar entry returned by get_current_season()."""
    if not season_entry:
        return None
    for entry in data.get("seasonal_calendar", []):
        if entry is season_entry:
            return entry.get("season")
    return None


def _condition_keyword_score(crop_stage, recent_weather, conditions_text):
    """
    Each pest's risk_factors.conditions is a short free-text list
    (e.g. "young palms 3-8 years", "high humidity") rather than a fixed
    schema, since real-world risk factors don't reduce cleanly to
    enum values. This does a simple keyword match against the
    farmer's crop_stage/recent_weather answers instead of requiring an
    exact match.
    """
    text = " ".join(conditions_text).lower()
    score = 0
    if crop_stage and crop_stage in text:
        score += 1
    if recent_weather == "humid" and ("humid" in text or "humidity" in text):
        score += 1
    if recent_weather == "dry" and ("dry" in text or "hot" in text):
        score += 1
    if recent_weather == "rainy" and ("rain" in text or "monsoon" in text):
        score += 1
    return score


def predict_pest_risk(crop_key, answers, image_path=None, month=None):
    """
    Main entry point, intended to be called by routes/pest.py.

    Returns a dict with:
        predicted_pest, pest_risk_score, risk_level, risk_meter,
        symptoms, management
    """
    data = load_crop_data(crop_key)
    pests = data.get("pests", [])
    season_entry = get_current_season(crop_key, month)
    current_season_key = _season_key_of(data, season_entry)

    best = None
    best_score = -1

    for pest in pests:
        risk_factors = pest.get("risk_factors", {})
        season_match = bool(current_season_key) and current_season_key in risk_factors.get("season", [])
        keyword_score = _condition_keyword_score(
            answers.get("crop_stage"), answers.get("recent_weather"), risk_factors.get("conditions", [])
        )

        if not season_match and keyword_score == 0:
            continue

        score = SIGHTING_WEIGHT.get(answers.get("pest_sightings"), 0)
        score += 15 if season_match else 0
        score += keyword_score * 10
        if image_path:
            score += 5  # small confidence boost when a photo was provided
        score = clamp(score)

        if score > best_score:
            best, best_score = pest, score

    if best is None or best_score <= 0:
        risk = build_risk_meter(5)
        return {
            "predicted_pest": "No significant pest risk detected",
            "pest_risk_score": 5.0,
            "risk_level": risk["level"],
            "risk_meter": risk,
            "symptoms": [],
            "management": ["Continue routine field monitoring."],
        }

    risk = build_risk_meter(best_score)
    return {
        "predicted_pest": best["name"],
        "pest_risk_score": risk["score"],
        "risk_level": risk["level"],
        "risk_meter": risk,
        "symptoms": best.get("symptoms", []),
        "management": best.get("management", []),
    }