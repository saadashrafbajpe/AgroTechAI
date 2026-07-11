"""
routes/disease.py
------------------
AI Crop Disease Detection.

Farmer answers 5 required questions about the plant's condition;
uploading a photo is optional but improves accuracy. Results are
scored locally by ai/disease_detector.py and stored in SQLite.
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

from ai.disease_detector import analyze_disease
from utils.image_processing import save_upload
from utils.database import create_session_if_missing, insert_disease_record

disease_bp = Blueprint("disease", __name__)

DISEASE_QUESTIONS = [
    ("affected_part", "Which part of the plant is most affected?",
     [("leaves", "Leaves"), ("stem_trunk", "Stem / Trunk"), ("roots", "Roots"),
      ("crown_bud", "Crown / Bud"), ("fruit_nut", "Fruit / Nut")]),
    ("discoloration", "What discoloration do you see?",
     [("none", "None"), ("yellowing", "Yellowing"), ("browning", "Browning"), ("blackening", "Blackening")]),
    ("odor_ooze", "Any foul smell or oozing from the plant?",
     [("yes", "Yes"), ("no", "No")]),
    ("onset_speed", "How quickly did symptoms appear?",
     [("sudden", "Suddenly (within days)"), ("gradual", "Gradually (over weeks)")]),
    ("spread", "Are the symptoms localized or spreading?",
     [("localized", "Localized"), ("spreading", "Spreading")]),
]


@disease_bp.route("/disease", methods=["GET", "POST"])
def disease():
    if "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    crop_key = session["crop_key"]

    if request.method == "POST":
        answers = {key: request.form.get(key) for key, _, _ in DISEASE_QUESTIONS}
        if not all(answers.values()):
            flash("Please answer all five questions.")
            return redirect(url_for("disease.disease"))

        image_path = save_upload(request.files.get("image"), prefix="disease")

        result = analyze_disease(crop_key, answers, image_path)

        session_id = create_session_if_missing(session, crop_key)
        insert_disease_record(
            session_id=session_id,
            crop_key=crop_key,
            answers=answers,
            image_path=image_path,
            detected_disease=result["detected_disease"],
            health_score=result["health_score"],
            risk_level=result["risk_level"],
        )

        return render_template("disease.html", questions=DISEASE_QUESTIONS, result=result, submitted=True)

    return render_template("disease.html", questions=DISEASE_QUESTIONS, result=None, submitted=False)