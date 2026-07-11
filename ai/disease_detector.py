"""
ai/disease_detector.py
-------------------------
AI Crop Disease Detection. Matches the farmer's 5-question
questionnaire (see DISEASE_QUESTIONS in routes/disease.py) against the
crop's local disease knowledge base (crop_data/<crop>.json ->
"diseases"), optionally nudged by a lightweight image heuristic when a
photo is provided. Entirely rule-based and offline.

Swap-in seam for a real trained model later: flip
Config.USE_TRAINED_MODEL to True (add this flag to config.py when
ready) and route analyze_disease() to a _model_based_predict()
function with the same return shape as _healthy_default()/the match
below - nothing in routes/disease.py or the templates needs to change.
"""

from ai.crop_health import load_crop_data
from ai.risk_meter import build_risk_meter
from utils.calculations import clamp

# Must stay in sync with DISEASE_QUESTIONS keys in routes/disease.py
MATCH_FIELDS = ["affected_part", "discoloration", "odor_ooze", "onset_speed", "spread"]

# Minimum number of matching fields required before a disease is
# considered detected at all, rather than guessing on weak evidence.
MIN_MATCH_THRESHOLD = 3


def _criteria_score(answers, match_criteria):
    """
    Scores how well the farmer's answers match one disease's
    match_criteria dict from crop_data. Each field's expected value can
    be a single string or a list of acceptable values.
    Returns (matched_count, total_fields_defined_for_this_disease).
    """
    matched = 0
    total = 0
    for field in MATCH_FIELDS:
        if field not in match_criteria:
            continue
        total += 1
        expected = match_criteria[field]
        actual = answers.get(field)
        if isinstance(expected, list):
            if actual in expected:
                matched += 1
        elif actual == expected:
            matched += 1
    return matched, total


def _image_confidence_multiplier(image_path):
    """
    Isolated seam for future OpenCV/TFLite image analysis (color
    heuristics for yellowing/browning, contour-based spot/lesion
    detection, edge density for wilting). Currently returns a small
    fixed boost when a photo is present, since farmers tend to only
    upload one when symptoms are visually obvious - replace the body
    of this function with real image analysis when a model exists.
    """
    if not image_path:
        return 1.0
    return 1.08


def analyze_disease(crop_key, answers, image_path=None):
    """
    Main entry point, called by routes/disease.py.

    Returns a dict with:
        detected_disease, causal_agent, confidence, health_score,
        risk_level, risk_meter, symptoms, treatment, prevention,
        matched_criteria
    """
    data = load_crop_data(crop_key)
    diseases = data.get("diseases", [])

    best = None
    best_matched = -1
    best_total = 0

    for disease in diseases:
        matched, total = _criteria_score(answers, disease.get("match_criteria", {}))
        if total == 0:
            continue
        if matched >= MIN_MATCH_THRESHOLD and matched > best_matched:
            best, best_matched, best_total = disease, matched, total

    if best is None:
        return _healthy_default()

    confidence = clamp((best_matched / best_total) * 100 * _image_confidence_multiplier(image_path))

    severity_weight = best.get("severity_weight", 50)
    health_score = clamp(100 - (severity_weight * (confidence / 100)))
    risk = build_risk_meter(100 - health_score)

    return {
        "detected_disease": best["name"],
        "causal_agent": best.get("causal_agent"),
        "confidence": round(confidence, 1),
        "health_score": round(health_score, 1),
        "risk_level": risk["level"],
        "risk_meter": risk,
        "symptoms": best.get("symptoms", []),
        "treatment": best.get("treatment", []),
        "prevention": best.get("prevention", []),
        "matched_criteria": f"{best_matched}/{best_total}",
    }


def _healthy_default():
    """Returned when no disease crosses MIN_MATCH_THRESHOLD - i.e. the
    plant appears healthy based on the farmer's answers."""
    risk = build_risk_meter(5)
    return {
        "detected_disease": "No disease detected",
        "causal_agent": None,
        "confidence": 0.0,
        "health_score": 95.0,
        "risk_level": risk["level"],
        "risk_meter": risk,
        "symptoms": [],
        "treatment": ["Continue routine monitoring and good field hygiene."],
        "prevention": [],
        "matched_criteria": "0/0",
    }