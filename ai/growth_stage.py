"""
ai/growth_stage.py
---------------------
Growth Stage Detection. The farmer answers 5 mandatory questions about
the plant's physical characteristics and may optionally upload an
image. Computes a 0-100 maturity score and maps it onto the crop's
growth_stages score_band from crop_data/<crop>.json.

ASSUMED FORM FIELDS (routes/growth.py wasn't available when this was
written) - update GROWTH_FIELDS/_maturity_score below if your actual
questionnaire differs:
    trunk_visible:     "yes" | "no"
    leaf_count:        "few" | "moderate" | "many"
    flowering_present: "yes" | "no"
    fruit_present:     "yes" | "no"
    height_category:   "short" | "medium" | "tall"
"""

from ai.crop_health import load_crop_data
from utils.calculations import clamp, score_to_band

# Keep in sync with the form fields collected in routes/growth.py
GROWTH_FIELDS = ["trunk_visible", "leaf_count", "flowering_present", "fruit_present", "height_category"]

LEAF_COUNT_SCORE = {"few": 5, "moderate": 12, "many": 20}
HEIGHT_SCORE = {"short": 5, "medium": 15, "tall": 25}


def _maturity_score(answers):
    """
    Combines the questionnaire answers into a single 0-100 maturity
    score. The weighting mirrors the natural progression every crop in
    crop_data.json follows: vegetative growth -> trunk/height increase
    -> flowering -> fruiting -> harvest maturity.
    """
    score = 0
    if answers.get("trunk_visible") == "yes":
        score += 20
    score += LEAF_COUNT_SCORE.get(answers.get("leaf_count"), 0)
    score += HEIGHT_SCORE.get(answers.get("height_category"), 0)
    if answers.get("flowering_present") == "yes":
        score += 20
    if answers.get("fruit_present") == "yes":
        score += 25
    return clamp(score)


def _image_adjustment(image_path):
    """
    Isolated seam for future CV-based maturity estimation (e.g. canopy
    size or fruit-color analysis via OpenCV/TFLite). Currently a no-op
    so routes/growth.py can pass an image today without any code
    changes needed when real image analysis is added later.
    """
    return 1.0


def detect_growth_stage(crop_key, answers, image_path=None):
    """
    Main entry point, intended to be called by routes/growth.py.

    Returns a dict with:
        detected_stage, stage_score, typical_age, characteristics,
        care_focus
    """
    data = load_crop_data(crop_key)
    stages = data.get("growth_stages", [])

    score = clamp(_maturity_score(answers) * _image_adjustment(image_path))

    bands = [
        {"min": s["score_band"]["min"], "max": s["score_band"]["max"], "stage": s}
        for s in stages
    ]
    band = score_to_band(score, bands)

    if band is None:
        return {
            "detected_stage": "Unknown",
            "stage_score": round(score, 1),
            "typical_age": None,
            "characteristics": [],
            "care_focus": [],
        }

    stage = band["stage"]
    return {
        "detected_stage": stage["name"],
        "stage_score": round(score, 1),
        "typical_age": stage.get("typical_age"),
        "characteristics": stage.get("characteristics", []),
        "care_focus": stage.get("care_focus", []),
    }