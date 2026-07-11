"""
routes/dashboard.py
--------------------
Dashboard Blueprint for AgroEdge.

Pulls the latest disease, pest, weather, and growth records for the
active session from the local SQLite database, combines them through
the ai/ decision-support modules, and renders the Crop Health Score,
Daily AI Advice, and Priority-Based Action List.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash

from utils.database import get_latest_for_session
from utils.helpers import load_crop_data, get_current_season
from ai.crop_health import compute_crop_health
from ai.advice_engine import generate_daily_advice
from ai.priority_engine import build_priority_action_list
from ai.risk_meter import risk_level_from_score

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard():
    if "session_id" not in session or "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    session_id = session["session_id"]
    crop_key = session["crop_key"]
    field_name = session.get("field_name")

    crop = load_crop_data(crop_key)
    latest = get_latest_for_session(session_id)

    disease_row = latest.get("disease")
    pest_row = latest.get("pest")
    weather_row = latest.get("weather")
    growth_row = latest.get("growth")

    have_all = all([disease_row, pest_row, weather_row, growth_row])

    context = {
        "crop": crop,
        "crop_key": crop_key,
        "field_name": field_name,
        "have_all": have_all,
        "missing": [],
        "composite_score": None,
        "risk_level": None,
        "risk_color": None,
        "advice": [],
        "actions": [],
        "season": get_current_season(),
    }

    if not have_all:
        if not disease_row:
            context["missing"].append(("Disease Detection", "disease.disease"))
        if not pest_row:
            context["missing"].append(("Pest Risk", "pest.pest"))
        if not weather_row:
            context["missing"].append(("Weather Risk", "weather.weather"))
        if not growth_row:
            context["missing"].append(("Growth Stage", "growth.growth"))
        return render_template("dashboard.html", **context)

    # --- Reconstruct module results from stored records ---
    disease_result = {
        "health_score": disease_row["health_score"],
        "risk_level": disease_row["risk_level"],
        "detected_disease": disease_row["detected_disease"],
    }
    pest_result = {
        "pest_risk_score": pest_row["pest_risk_score"],
        "risk_level": pest_row["risk_level"],
        "predicted_pest": pest_row["predicted_pest"],
    }
    weather_result = {
        "weather_risk_score": weather_row["weather_risk_score"],
        "risk_level": weather_row["risk_level"],
        "dominant_risk": weather_row["dominant_risk"],
    }
    growth_result = {
        "stage_label": growth_row["detected_stage"],
        "stage_score": growth_row["stage_score"],
    }

    # --- Composite Crop Health Score + Risk Meter ---
    composite_score = compute_crop_health(disease_result, pest_result, weather_result)
    risk_label, risk_color = risk_level_from_score(100 - composite_score)

    # --- Daily AI Advice ---
    advice = generate_daily_advice(
        crop_key, disease_result, pest_result, weather_result, growth_result
    )

    # --- Priority-Based Action List ---
    actions = build_priority_action_list(
        disease_result, pest_result, weather_result, growth_result
    )

    context.update({
        "composite_score": composite_score,
        "risk_level": risk_label,
        "risk_color": risk_color,
        "advice": advice,
        "actions": actions,
        "disease_result": disease_result,
        "pest_result": pest_result,
        "weather_result": weather_result,
        "growth_result": growth_result,
    })

    return render_template("dashboard.html", **context)


@dashboard_bp.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))