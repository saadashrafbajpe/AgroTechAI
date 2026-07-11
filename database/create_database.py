"""
database/create_database.py
----------------------------
Creates the local SQLite schema for AgroEdge at database/agroedge.db.
Run directly to (re)initialize the database, or import create_database()
and call it from app.py on startup — safe to run repeatedly since every
statement uses IF NOT EXISTS.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "agroedge.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_key TEXT NOT NULL,
    field_name TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS disease_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    crop_key TEXT NOT NULL,
    answers TEXT NOT NULL,
    image_path TEXT,
    detected_disease TEXT,
    health_score REAL,
    risk_level TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS pest_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    crop_key TEXT NOT NULL,
    answers TEXT NOT NULL,
    predicted_pest TEXT,
    pest_risk_score REAL,
    risk_level TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS weather_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    crop_key TEXT NOT NULL,
    answers TEXT NOT NULL,
    weather_risk_score REAL,
    risk_level TEXT,
    dominant_risk TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS growth_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    crop_key TEXT NOT NULL,
    answers TEXT NOT NULL,
    image_path TEXT,
    detected_stage TEXT,
    stage_score REAL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS advisory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    crop_key TEXT NOT NULL,
    advice_text TEXT NOT NULL,
    priority_actions TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_disease_session ON disease_records(session_id);
CREATE INDEX IF NOT EXISTS idx_pest_session ON pest_records(session_id);
CREATE INDEX IF NOT EXISTS idx_weather_session ON weather_records(session_id);
CREATE INDEX IF NOT EXISTS idx_growth_session ON growth_records(session_id);
CREATE INDEX IF NOT EXISTS idx_advisory_session ON advisory_log(session_id);
"""


def create_database(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"[AgroEdge] Database initialized at {db_path}")


if __name__ == "__main__":
    create_database()