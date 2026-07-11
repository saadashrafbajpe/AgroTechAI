"""
routes/pest.py
---------------
Pest Risk Predictor.

Estimates the likelihood of pest infestation from the farmer's
observations, crop type, and current seasonal pressure, using
ai/pest_predictor.py. Predicts risk before severe damage occurs
rather than only confirming existing infestations.
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

from ai.pest_predictor import predict_pest_risk
from utils.database import create_session_if_missing, insert_pest_record

pest_bp = Blueprint("pest", __name__)

PEST_QUESTIONS = [
    ("visible_insects", "Have you seen insects on the plant?",
     [("yes", "Yes"), ("no", "No")]),
    ("damage_pattern", "What damage pattern is visible?",
     [("none", "None"), ("chewed_leaves", "Chewed leaves"), ("cut_marks", "Cut marks / holes"), ("wilting", "Wilting")]),
    ("sticky_residue", "Any sticky residue or sooty mould?",
     [("yes", "Yes"), ("no", "No")]),
    ("boring_holes", "Any boring holes or gum/frass exudation?",
     [("yes", "Yes"), ("no", "No")]),
    ("season_pressure", "Is the current season known for high pest activity here?",
     [("high", "High"), ("low", "Low")]),
]


@pest_bp.route("/pest", methods=["GET", "POST"])
def pest():
    if "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    crop_key = session["crop_key"]

    if request.method == "POST":
        answers = {key: request.form.get(key) for key, _, _ in PEST_QUESTIONS}
        if not all(answers.values()):
            flash("Please answer all five questions.")
            return redirect(url_for("pest.pest"))

        result = predict_pest_risk(crop_key, answers)

        session_id = create_session_if_missing(session, crop_key)
        insert_pest_record(
            session_id=session_id,
            crop_key=crop_key,
            answers=answers,
            predicted_pest=result["predicted_pest"],
            pest_risk_score=result["pest_risk_score"],
            risk_level=result["risk_level"],
        )

        return render_template("pest.html", questions=PEST_QUESTIONS, result=result, submitted=True)

    return render_template("pest.html", questions=PEST_QUESTIONS, result=None, submitted=False)