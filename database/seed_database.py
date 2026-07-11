"""
database/seed_database.py
---------------------------
Seeds the crops table from the offline crop_data/*.json files
(coconut, arecanut, rice, rubber, cashew). Safe to re-run — uses
INSERT OR IGNORE so existing rows are left untouched.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "agroedge.db")
CROP_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "crop_data")


def seed_database(db_path=DB_PATH, crop_data_dir=CROP_DATA_DIR):
    if not os.path.isdir(crop_data_dir):
        raise FileNotFoundError(f"crop_data directory not found at {crop_data_dir}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    seeded = 0

    for filename in sorted(os.listdir(crop_data_dir)):
        if not filename.endswith(".json"):
            continue
        crop_key = filename.replace(".json", "")
        with open(os.path.join(crop_data_dir, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
        cur.execute(
            "INSERT OR IGNORE INTO crops (crop_key, name) VALUES (?, ?)",
            (crop_key, data.get("name", crop_key.title())),
        )
        seeded += cur.rowcount

    conn.commit()
    conn.close()
    print(f"[AgroEdge] Crop table seeded ({seeded} new crop(s) added) from {crop_data_dir}")


if __name__ == "__main__":
    seed_database()