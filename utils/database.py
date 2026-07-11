"""
utils/database.py
-------------------
Thin SQLite helper layer used by every Blueprint in routes/. Kept
dependency-free (stdlib sqlite3 only) so the whole stack runs on a
bare edge device with no external database server. Assumes the schema
has already been created via database/create_database.py.
"""

import json
import sqlite3

from config import Config


def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def create_session(crop_key, field_name=None):
    """Inserts a new monitoring session and returns its id."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO sessions (crop_key, field_name) VALUES (?, ?)",
        (crop_key, field_name),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def create_session_if_missing(flask_session, crop_key, field_name=None):
    """
    Reuses the active session stored in the Flask session cookie if it
    already matches this crop, otherwise creates a new one and stores
    it back into the Flask session. Used by every questionnaire route
    so repeated submissions accumulate under the same session_id.
    """
    if flask_session.get("session_id") and flask_session.get("crop_key") == crop_key:
        return flask_session["session_id"]

    session_id = create_session(crop_key, field_name)
    flask_session["session_id"] = session_id
    flask_session["crop_key"] = crop_key
    if field_name:
        flask_session["field_name"] = field_name
    return session_id


def get_session(session_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_sessions(limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Disease records
# ---------------------------------------------------------------------------
def insert_disease_record(session_id, crop_key, answers, image_path,
                           detected_disease, health_score, risk_level):
    conn = get_connection()
    conn.execute(
        """INSERT INTO disease_records
           (session_id, crop_key, answers, image_path, detected_disease, health_score, risk_level)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, crop_key, json.dumps(answers), image_path,
         detected_disease, health_score, risk_level),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Pest records
# ---------------------------------------------------------------------------
def insert_pest_record(session_id, crop_key, answers, predicted_pest,
                        pest_risk_score, risk_level):
    conn = get_connection()
    conn.execute(
        """INSERT INTO pest_records
           (session_id, crop_key, answers, predicted_pest, pest_risk_score, risk_level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, crop_key, json.dumps(answers), predicted_pest,
         pest_risk_score, risk_level),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Weather records
# ---------------------------------------------------------------------------
def insert_weather_record(session_id, crop_key, answers, weather_risk_score,
                           risk_level, dominant_risk):
    conn = get_connection()
    conn.execute(
        """INSERT INTO weather_records
           (session_id, crop_key, answers, weather_risk_score, risk_level, dominant_risk)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, crop_key, json.dumps(answers), weather_risk_score,
         risk_level, dominant_risk),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Growth records
# ---------------------------------------------------------------------------
def insert_growth_record(session_id, crop_key, answers, image_path,
                          detected_stage, stage_score):
    conn = get_connection()
    conn.execute(
        """INSERT INTO growth_records
           (session_id, crop_key, answers, image_path, detected_stage, stage_score)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, crop_key, json.dumps(answers), image_path,
         detected_stage, stage_score),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Advisory log
# ---------------------------------------------------------------------------
def insert_advisory_log(session_id, crop_key, advice_text, priority_actions):
    conn = get_connection()
    conn.execute(
        """INSERT INTO advisory_log (session_id, crop_key, advice_text, priority_actions)
           VALUES (?, ?, ?, ?)""",
        (session_id, crop_key, advice_text, json.dumps(priority_actions)),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Aggregate reads (dashboard + reports)
# ---------------------------------------------------------------------------
def get_latest_for_session(session_id):
    """Pulls the most recent record from each module for a session —
    used by the dashboard to compute today's Crop Health Score."""
    conn = get_connection()
    result = {}
    for table, key in [
        ("disease_records", "disease"),
        ("pest_records", "pest"),
        ("weather_records", "weather"),
        ("growth_records", "growth"),
    ]:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        result[key] = dict(row) if row else None
    conn.close()
    return result


def get_session_records(session_id):
    """Pulls the FULL history (not just latest) from each module for a
    session — used by the report view."""
    conn = get_connection()
    result = {}
    for table, key in [
        ("disease_records", "disease"),
        ("pest_records", "pest"),
        ("weather_records", "weather"),
        ("growth_records", "growth"),
    ]:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE session_id = ? ORDER BY id DESC",
            (session_id,),
        ).fetchall()
        result[key] = [dict(r) for r in rows]
    conn.close()
    return result