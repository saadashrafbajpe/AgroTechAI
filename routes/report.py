"""
routes/reports.py
------------------
History Report.

Shows the full local history for the active session — every disease,
pest, weather, and growth record generated so far — plus a list of
past monitoring sessions stored on this edge device.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash

from utils.database import get_session_records, get_recent_sessions
from utils.helpers import load_crop_data

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports")
def report():
    if "session_id" not in session or "crop_key" not in session:
        flash("Please select a crop to begin monitoring.")
        return redirect(url_for("index"))

    session_id = session["session_id"]
    crop_key = session["crop_key"]
    crop = load_crop_data(crop_key)

    records = get_session_records(session_id)

    return render_template(
        "report.html",
        crop=crop,
        field_name=session.get("field_name"),
        disease_records=records["disease"],
        pest_records=records["pest"],
        weather_records=records["weather"],
        growth_records=records["growth"],
    )


@reports_bp.route("/reports/history")
def history():
    """Overview of past monitoring sessions on this device, most recent first."""
    sessions = get_recent_sessions(limit=20)

    return render_template(
        "report_history.html",
        sessions=sessions,
    )