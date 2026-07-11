"""
routes/growth.py
-----------------
Growth Stage Detection.

Farmer answers 5 mandatory questions about the plant's physical
characteristics; an image upload is optional. ai/growth_stage.py
maps the result onto the crop's predefined growth-stage bands so
all other advisory modules can be tailored to that stage.
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

from ai.growth_stage import detect_growth_stage
from utils.image_processing import save_upload
from utils.database import create_session_if_missing, insert_growth_record

growth_bp = Blueprint("growth", __name__)

GROWTH_QUESTIONS = [
    ("height_category", "Plant height category?",
     [("very_small", "Very small"), ("small", "Small"), ("medium", "Medium"),
      ("tall", "Tall"), ("full_height", "Full height")]),
    ("leaf_condition", "Leaf condition?",
     [("few_leaves", "Few leaves"), ("moderate_leaves", "Moderate leaves"),
      ("dense_leaves", "Dense leaves"), ("thinning_leaves", "Thinning leaves")]),
    ("flowering_fruiting", "Flowering / fruiting status?",
     [("none", "None"), ("flowering", "Flowering"), ("fruiting", "Fruiting"),
      ("heavy_yield", "Heavy yield"), ("declining_yield", "Declining yield")]),
    ("trunk_girth", "Trunk / stem girth?",
     [("very_thin", "Very thin"), ("thin", "Thin"), ("moderate", "Moderate"),
      ("thick", "Thick"), ("very_thick", "Very thick")]),
    ("canopy_density", "Canopy density?",
     [("sparse", "Sparse"), ("developing", "Developing"), ("full", "Full"), ("very_full", "Very full")]),
]


@growth_bp.route("/growth", methods=["GET", "POST"])
def growth():
    if "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    crop_key = session["crop_key"]

    if request.method == "POST":
        answers = {key: request.form.get(key) for key, _, _ in GROWTH_QUESTIONS}
        if not all(answers.values()):
            flash("Please answer all five questions.")
            return redirect(url_for("growth.growth"))

        image_path = save_upload(request.files.get("image"), prefix="growth")

        result = detect_growth_stage(crop_key, answers, image_path)

        session_id = create_session_if_missing(session, crop_key)
        insert_growth_record(
            session_id=session_id,
            crop_key=crop_key,
            answers=answers,
            image_path=image_path,
            detected_stage=result["stage_label"],
            stage_score=result["stage_score"],
        )

        return render_template("growth.html", questions=GROWTH_QUESTIONS, result=result, submitted=True)

    return render_template("growth.html", questions=GROWTH_QUESTIONS, result=None, submitted=False)