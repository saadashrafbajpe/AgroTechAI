"""
routes/weather.py
------------------
Offline Weather Risk Predictor.

No internet-based forecast is used. The farmer answers 5 questions
about current local conditions; ai/weather_predictor.py combines
these with preloaded seasonal knowledge to estimate weather risk.
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, flash

from ai.weather_predictor import predict_weather_risk
from utils.database import create_session_if_missing, insert_weather_record

weather_bp = Blueprint("weather", __name__)

WEATHER_QUESTIONS = [
    ("rainfall", "Rainfall observed in the last few days?",
     [("none", "None"), ("light", "Light"), ("heavy", "Heavy")]),
    ("cloud_cover", "Current cloud cover?",
     [("clear", "Clear"), ("partly", "Partly cloudy"), ("overcast", "Overcast")]),
    ("wind", "Wind conditions?",
     [("calm", "Calm"), ("moderate", "Moderate"), ("strong", "Strong")]),
    ("temperature", "How does the temperature feel?",
     [("normal", "Normal"), ("hot", "Hot"), ("cold", "Cold")]),
    ("humidity", "Humidity level?",
     [("low", "Low"), ("normal", "Normal"), ("high", "High")]),
]


@weather_bp.route("/weather", methods=["GET", "POST"])
def weather():
    if "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    crop_key = session["crop_key"]

    if request.method == "POST":
        answers = {key: request.form.get(key) for key, _, _ in WEATHER_QUESTIONS}
        if not all(answers.values()):
            flash("Please answer all five questions.")
            return redirect(url_for("weather.weather"))

        result = predict_weather_risk(answers)

        session_id = create_session_if_missing(session, crop_key)
        insert_weather_record(
            session_id=session_id,
            crop_key=crop_key,
            answers=answers,
            weather_risk_score=result["weather_risk_score"],
            risk_level=result["risk_level"],
            dominant_risk=result["dominant_risk"],
        )

        return render_template("weather.html", questions=WEATHER_QUESTIONS, result=result, submitted=True)

    return render_template("weather.html", questions=WEATHER_QUESTIONS, result=None, submitted=False)