"""
AgroEdge — Offline Edge-Based Intelligent Crop Monitoring & Decision Support
=============================================================================
A single self-contained Flask application. No internet connection, cloud
service, or external API is required at runtime: all crop knowledge
(diseases, pests, growth stages, seasonal advisories) is preloaded in this
file, all history is stored in a local SQLite database, and every
"AI" module below is a transparent, deterministic scoring engine driven by
the farmer's questionnaire answers (plus a lightweight local image heuristic
when a photo is supplied). This keeps the whole stack runnable on a
low-power edge device with just Python + Flask + Pillow.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000/
"""

import io
import json
import os
import sqlite3
from datetime import datetime, timedelta

from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, flash, send_from_directory
)
from werkzeug.utils import secure_filename

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "agroedge.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "agroedge-offline-edge-key"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)


# ---------------------------------------------------------------------------
# Preloaded offline crop knowledge base
# ---------------------------------------------------------------------------
CROP_DATA = {
    "coconut": {
        "name": "Coconut",
        "growth_stages": [
            {"id": "seedling", "label": "Seedling (0-1 yr)", "min": 0, "max": 20},
            {"id": "juvenile", "label": "Juvenile (1-4 yrs)", "min": 21, "max": 45},
            {"id": "pre_bearing", "label": "Pre-bearing (4-6 yrs)", "min": 46, "max": 65},
            {"id": "bearing", "label": "Bearing / Productive", "min": 66, "max": 90},
            {"id": "senile", "label": "Senile / Old palm", "min": 91, "max": 100},
        ],
        "diseases": [
            {"name": "Bud Rot", "treatment": "Remove and burn affected tissue, apply Bordeaux paste on the wound, and spray 1% Bordeaux mixture on the crown."},
            {"name": "Leaf Rot", "treatment": "Apply a neem-based fungicide, improve drainage, and remove infected leaves."},
            {"name": "Root (Wilt) Disease", "treatment": "Balanced potassium fertilization; remove severely affected palms; apply bio-control agents."},
            {"name": "Stem Bleeding", "treatment": "Scrape the bleeding patch, apply Bordeaux paste, and improve drainage."},
        ],
        "pests": ["Rhinoceros Beetle", "Red Palm Weevil", "Coconut Eriophyid Mite"],
        "seasonal_advisory": {
            "summer": "Irrigate every 3-4 days with 40-50 litres/palm; mulch basins to conserve moisture; watch for mite damage on young nuts.",
            "monsoon": "Ensure proper drainage in basins; apply organic manure; watch for bud rot and leaf rot after continuous rain.",
            "post_monsoon": "Apply the recommended NPK dose; remove dried/diseased leaves; check for rhinoceros beetle damage.",
            "winter": "Reduce irrigation frequency; apply potassium-rich fertilizer to boost disease resistance; inspect the crown region.",
        },
    },
    "arecanut": {
        "name": "Arecanut",
        "growth_stages": [
            {"id": "seedling", "label": "Seedling (0-1 yr)", "min": 0, "max": 20},
            {"id": "juvenile", "label": "Juvenile (1-3 yrs)", "min": 21, "max": 45},
            {"id": "pre_bearing", "label": "Pre-bearing (3-5 yrs)", "min": 46, "max": 65},
            {"id": "bearing", "label": "Bearing / Productive", "min": 66, "max": 90},
            {"id": "senile", "label": "Senile / Old palm", "min": 91, "max": 100},
        ],
        "diseases": [
            {"name": "Mahali / Fruit Rot", "treatment": "Spray 1% Bordeaux mixture before monsoon and repeat after 45 days; remove and destroy fallen nuts."},
            {"name": "Yellow Leaf Disease", "treatment": "Apply balanced fertilizer with micronutrients; remove severely affected palms; avoid waterlogging."},
            {"name": "Bud Rot", "treatment": "Remove the infected spindle, apply copper fungicide paste, drench the crown with fungicide solution."},
        ],
        "pests": ["Spindle Bug", "Root Grub"],
        "seasonal_advisory": {
            "summer": "Irrigate at 4-day intervals; mulch basins with arecanut husk; monitor for spindle bug activity.",
            "monsoon": "Ensure basin drainage; apply Bordeaux spray as prophylaxis against fruit rot.",
            "post_monsoon": "Apply the recommended fertilizer dose; remove fallen diseased nuts from the plot.",
            "winter": "Light irrigation; inspect the crown for early bud rot symptoms; apply organic mulch.",
        },
    },
    "rice": {
        "name": "Rice",
        "growth_stages": [
            {"id": "seedling", "label": "Seedling / Nursery", "min": 0, "max": 15},
            {"id": "tillering", "label": "Tillering", "min": 16, "max": 40},
            {"id": "panicle_initiation", "label": "Panicle Initiation", "min": 41, "max": 60},
            {"id": "flowering", "label": "Flowering / Heading", "min": 61, "max": 80},
            {"id": "maturity", "label": "Grain Filling / Maturity", "min": 81, "max": 100},
        ],
        "diseases": [
            {"name": "Rice Blast", "treatment": "Spray a tricyclazole-based fungicide, avoid excess nitrogen, use resistant varieties next season."},
            {"name": "Bacterial Leaf Blight", "treatment": "Drain the field temporarily, avoid overhead irrigation, apply a copper-based bactericide."},
            {"name": "Sheath Blight", "treatment": "Reduce plant density, apply a validamycin-based fungicide, maintain field sanitation."},
        ],
        "pests": ["Yellow Stem Borer", "Brown Planthopper", "Rice Leaf Folder"],
        "seasonal_advisory": {
            "summer": "Maintain shallow standing water; watch for stem borer during the vegetative stage.",
            "monsoon": "Ensure proper field drainage during heavy rain; monitor for bacterial blight and blast.",
            "post_monsoon": "Apply top-dressing of nitrogen at panicle initiation; scout for brown planthopper.",
            "winter": "Maintain a thin film of water; protect against cold-induced sterility at flowering.",
        },
    },
    "rubber": {
        "name": "Rubber",
        "growth_stages": [
            {"id": "nursery", "label": "Nursery Stage", "min": 0, "max": 15},
            {"id": "immature", "label": "Immature (1-6 yrs)", "min": 16, "max": 50},
            {"id": "tappable", "label": "Tappable / Mature", "min": 51, "max": 85},
            {"id": "old_growth", "label": "Old Growth / Replanting Due", "min": 86, "max": 100},
        ],
        "diseases": [
            {"name": "Abnormal Leaf Fall", "treatment": "Spray copper oxychloride before and during monsoon; ensure canopy aeration."},
            {"name": "Pink Disease", "treatment": "Prune and burn affected branches, apply Bordeaux paste on cut surfaces."},
            {"name": "Powdery Mildew", "treatment": "Dust wettable sulphur early morning during the refoliation period."},
        ],
        "pests": ["Termites", "Scale Insects"],
        "seasonal_advisory": {
            "summer": "Apply mulch to conserve soil moisture; avoid tapping during extreme heat hours.",
            "monsoon": "Use rain guards on tapping panels; watch closely for abnormal leaf fall disease.",
            "post_monsoon": "Resume the normal tapping schedule; apply the recommended fertilizer mixture.",
            "winter": "Monitor for powdery mildew during refoliation; adjust tapping frequency.",
        },
    },
    "cashew": {
        "name": "Cashew",
        "growth_stages": [
            {"id": "seedling", "label": "Seedling (0-1 yr)", "min": 0, "max": 20},
            {"id": "vegetative", "label": "Vegetative Growth (1-3 yrs)", "min": 21, "max": 45},
            {"id": "flowering", "label": "Flowering / Fruiting Onset (3-4 yrs)", "min": 46, "max": 65},
            {"id": "bearing", "label": "Bearing / Productive", "min": 66, "max": 90},
            {"id": "senile", "label": "Senile / Declining Yield", "min": 91, "max": 100},
        ],
        "diseases": [
            {"name": "Die-Back", "treatment": "Prune affected twigs 15cm below infection, apply Bordeaux paste, spray copper fungicide."},
            {"name": "Anthracnose", "treatment": "Spray carbendazim during flowering and fruit set; remove infected plant debris."},
            {"name": "Pink Disease", "treatment": "Prune and destroy infected branches, apply Bordeaux paste on wounds."},
        ],
        "pests": ["Tea Mosquito Bug", "Stem and Root Borer"],
        "seasonal_advisory": {
            "summer": "Provide basin irrigation to young plants; mulch to retain moisture; watch for stem borer near the collar.",
            "monsoon": "Ensure drainage around the base; monitor for die-back after heavy rain.",
            "post_monsoon": "Apply the recommended fertilizer schedule; prune dead and diseased twigs.",
            "winter": "Spray against tea mosquito bug before and during flowering; avoid water stress at fruit set.",
        },
    },
}


# ---------------------------------------------------------------------------
# Database helpers (local SQLite — no external DB server)
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_key TEXT NOT NULL,
            field_name TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS disease_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            crop_key TEXT,
            answers TEXT,
            image_path TEXT,
            detected_disease TEXT,
            health_score REAL,
            risk_level TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS pest_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            crop_key TEXT,
            answers TEXT,
            predicted_pest TEXT,
            pest_risk_score REAL,
            risk_level TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            crop_key TEXT,
            answers TEXT,
            weather_risk_score REAL,
            risk_level TEXT,
            dominant_risk TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS growth_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            crop_key TEXT,
            answers TEXT,
            image_path TEXT,
            detected_stage TEXT,
            stage_score REAL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Small shared utilities
# ---------------------------------------------------------------------------
def get_current_season():
    month = datetime.now().month
    if month in (3, 4, 5):
        return "summer"
    if month in (6, 7, 8, 9):
        return "monsoon"
    if month in (10, 11):
        return "post_monsoon"
    return "winter"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def risk_level_from_score(score):
    """0-100 risk score -> (label, css color) used by the Risk Meter."""
    if score < 25:
        return "Low", "#2e7d32"
    if score < 50:
        return "Medium", "#f9a825"
    if score < 75:
        return "High", "#ef6c00"
    return "Critical", "#c62828"


def analyze_image_heuristic(filepath):
    """
    Lightweight, fully-offline visual heuristic (no cloud CV model):
    estimates the proportion of unhealthy (brown/yellow) vs healthy
    (green) pixels in the uploaded plant photo. Returns a 0-100
    'stress score' that nudges the questionnaire-based result — this
    is a supplement to the farmer's answers, not a replacement.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(filepath).convert("RGB")
        img.thumbnail((200, 200))
        pixels = list(img.getdata())
        if not pixels:
            return None
        unhealthy = 0
        for r, g, b in pixels:
            # crude green-vs-brown/yellow classification
            if g > r and g > b and g > 60:
                continue  # healthy green
            if r > 90 and g > 60 and b < 90:
                unhealthy += 1  # brown/yellow/dry tones
        return round((unhealthy / len(pixels)) * 100, 1)
    except Exception:
        return None


def save_upload(file_storage, prefix):
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(f"{prefix}_{int(datetime.now().timestamp())}_{file_storage.filename}")
    path = os.path.join(UPLOAD_DIR, filename)
    file_storage.save(path)
    return path


# ---------------------------------------------------------------------------
# "AI" decision-support modules
# Each is a transparent weighted scoring engine over the farmer's answers,
# optionally nudged by the offline image heuristic above. This is what
# actually runs on the edge device (no network calls, no cloud inference).
# ---------------------------------------------------------------------------
def analyze_disease(crop_key, answers, image_path=None):
    """
    answers keys: affected_part, discoloration, odor_ooze, onset_speed, spread
    Returns dict: health_score (0-100, higher = healthier), risk_level,
    color, likely_disease, treatment.
    """
    stress = 0
    if answers["affected_part"] in ("crown_bud", "roots"):
        stress += 25
    elif answers["affected_part"] in ("stem_trunk",):
        stress += 20
    else:
        stress += 10

    stress += {"none": 0, "yellowing": 15, "browning": 22, "blackening": 30}.get(answers["discoloration"], 10)
    stress += 20 if answers["odor_ooze"] == "yes" else 0
    stress += 20 if answers["onset_speed"] == "sudden" else 8
    stress += 15 if answers["spread"] == "spreading" else 5

    if image_path:
        img_stress = analyze_image_heuristic(image_path)
        if img_stress is not None:
            stress = round((stress * 0.7) + (img_stress * 0.3), 1)

    stress = min(stress, 100)
    health_score = round(100 - stress, 1)
    risk_label, color = risk_level_from_score(stress)

    crop = CROP_DATA[crop_key]
    # pick the most plausible disease from the offline knowledge base
    # using simple keyword matching on the affected part / symptoms given
    likely = crop["diseases"][0]
    part = answers["affected_part"]
    odor = answers["odor_ooze"] == "yes"
    for d in crop["diseases"]:
        name = d["name"].lower()
        if part == "crown_bud" and "bud" in name:
            likely = d
            break
        if part == "stem_trunk" and ("stem" in name or "bleeding" in name or "pink" in name):
            likely = d
            break
        if odor and ("rot" in name or "blight" in name):
            likely = d
            break

    detected = likely["name"] if stress >= 25 else "No significant disease indicators"
    treatment = likely["treatment"] if stress >= 25 else "Continue routine monitoring; no treatment needed at this time."

    return {
        "health_score": health_score,
        "stress_score": stress,
        "risk_level": risk_label,
        "color": color,
        "detected_disease": detected,
        "treatment": treatment,
    }


def predict_pest_risk(crop_key, answers):
    """
    answers keys: visible_insects, damage_pattern, sticky_residue, boring_holes, season_pressure
    """
    score = 0
    score += 25 if answers["visible_insects"] == "yes" else 5
    score += {"none": 0, "chewed_leaves": 15, "cut_marks": 20, "wilting": 18}.get(answers["damage_pattern"], 10)
    score += 15 if answers["sticky_residue"] == "yes" else 0
    score += 25 if answers["boring_holes"] == "yes" else 0
    score += 15 if answers["season_pressure"] == "high" else 5
    score = min(score, 100)

    risk_label, color = risk_level_from_score(score)
    crop = CROP_DATA[crop_key]
    idx = min(int(score // (100 / max(len(crop["pests"]), 1))), len(crop["pests"]) - 1)
    predicted_pest = crop["pests"][idx] if score >= 25 else "No significant pest pressure detected"

    return {
        "pest_risk_score": round(score, 1),
        "risk_level": risk_label,
        "color": color,
        "predicted_pest": predicted_pest,
    }


def predict_weather_risk(answers):
    """
    answers keys: rainfall, cloud_cover, wind, temperature, humidity
    Fully offline — derived only from the farmer's local observations.
    """
    score = 0
    contributions = {}

    r = {"none": 5, "light": 10, "heavy": 25}.get(answers["rainfall"], 10)
    score += r
    contributions["Excess rainfall / waterlogging"] = r

    c = {"clear": 5, "partly": 10, "overcast": 18}.get(answers["cloud_cover"], 10)
    score += c

    w = {"calm": 5, "moderate": 12, "strong": 22}.get(answers["wind"], 10)
    score += w
    contributions["Wind damage"] = w

    t = {"normal": 5, "hot": 20, "cold": 18}.get(answers["temperature"], 10)
    score += t
    contributions["Heat / cold stress"] = t

    h = {"low": 15, "normal": 5, "high": 18}.get(answers["humidity"], 10)
    score += h
    contributions["Humidity-related disease pressure"] = h

    score = min(round(score, 1), 100)
    risk_label, color = risk_level_from_score(score)
    dominant_risk = max(contributions, key=contributions.get)

    return {
        "weather_risk_score": score,
        "risk_level": risk_label,
        "color": color,
        "dominant_risk": dominant_risk,
    }


def detect_growth_stage(crop_key, answers, image_path=None):
    """
    answers keys: height_category, leaf_condition, flowering_fruiting, trunk_girth, canopy_density
    Each maps to a 0-100 maturity contribution; the aggregate is matched
    against the crop's predefined stage bands.
    """
    weights = {
        "height_category": {"very_small": 5, "small": 25, "medium": 50, "tall": 75, "full_height": 95},
        "leaf_condition": {"few_leaves": 10, "moderate_leaves": 40, "dense_leaves": 70, "thinning_leaves": 90},
        "flowering_fruiting": {"none": 10, "flowering": 55, "fruiting": 75, "heavy_yield": 90, "declining_yield": 97},
        "trunk_girth": {"very_thin": 5, "thin": 30, "moderate": 55, "thick": 80, "very_thick": 95},
        "canopy_density": {"sparse": 15, "developing": 45, "full": 70, "very_full": 90},
    }
    total, count = 0, 0
    for key, mapping in weights.items():
        val = answers.get(key)
        if val in mapping:
            total += mapping[val]
            count += 1

    stage_score = round(total / count, 1) if count else 50.0

    if image_path:
        img_stress = analyze_image_heuristic(image_path)
        if img_stress is not None:
            # thinning/aging foliage correlates with higher heuristic "stress" reading;
            # nudge maturity estimate slightly upward when present
            stage_score = round(min(stage_score + (img_stress * 0.1), 100), 1)

    crop = CROP_DATA[crop_key]
    stage = crop["growth_stages"][-1]
    for s in crop["growth_stages"]:
        if s["min"] <= stage_score <= s["max"]:
            stage = s
            break

    return {"stage_score": stage_score, "stage_label": stage["label"], "stage_id": stage["id"]}


def compute_crop_health(disease_result, pest_result, weather_result):
    """Weighted composite Crop Health Score shown on the dashboard."""
    disease_component = disease_result["health_score"]
    pest_component = 100 - pest_result["pest_risk_score"]
    weather_component = 100 - weather_result["weather_risk_score"]
    composite = round(
        (disease_component * 0.5) + (pest_component * 0.3) + (weather_component * 0.2), 1
    )
    return composite


def generate_daily_advice(crop_key, disease_result, pest_result, weather_result, growth_result):
    """Combines every module's output into a short daily briefing."""
    crop = CROP_DATA[crop_key]
    season = get_current_season()
    lines = [crop["seasonal_advisory"].get(season, "Continue standard seasonal care.")]

    if disease_result["risk_level"] in ("High", "Critical"):
        lines.append(f"Disease alert: {disease_result['detected_disease']} suspected — {disease_result['treatment']}")
    if pest_result["risk_level"] in ("High", "Critical"):
        lines.append(f"Pest alert: monitor closely for {pest_result['predicted_pest']}.")
    if weather_result["risk_level"] in ("High", "Critical"):
        lines.append(f"Weather caution: elevated risk of {weather_result['dominant_risk'].lower()} — take protective action today.")
    lines.append(f"Growth stage: {growth_result['stage_label']} — tailor fertilizer and water accordingly.")

    return lines


def build_priority_action_list(disease_result, pest_result, weather_result, growth_result):
    """Color-coded, urgency-sorted list for the dashboard."""
    actions = []

    def urgency_from_level(level):
        return {"Critical": (4, "#c62828"), "High": (3, "#ef6c00"), "Medium": (2, "#f9a825"), "Low": (1, "#2e7d32")}[level]

    rank, color = urgency_from_level(disease_result["risk_level"])
    actions.append({"title": f"Treat suspected {disease_result['detected_disease']}", "detail": disease_result["treatment"], "level": disease_result["risk_level"], "rank": rank, "color": color})

    rank, color = urgency_from_level(pest_result["risk_level"])
    actions.append({"title": f"Inspect for {pest_result['predicted_pest']}", "detail": "Scout affected plants and apply recommended control if confirmed.", "level": pest_result["risk_level"], "rank": rank, "color": color})

    rank, color = urgency_from_level(weather_result["risk_level"])
    actions.append({"title": f"Mitigate {weather_result['dominant_risk']}", "detail": "Adjust irrigation/drainage or protective measures today.", "level": weather_result["risk_level"], "rank": rank, "color": color})

    actions.append({"title": f"Growth-stage care for {growth_result['stage_label']}", "detail": "Apply stage-appropriate fertilizer and water schedule.", "level": "Low", "rank": 1, "color": "#2e7d32"})

    actions.sort(key=lambda a: a["rank"], reverse=True)
    return actions


# ---------------------------------------------------------------------------
# Shared HTML shell (kept inline so the whole app is a single file)
# ---------------------------------------------------------------------------
BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgroEdge — Offline Crop Decision Support</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background:#f4f7f2; }
  .navbar-brand { font-weight:700; letter-spacing:.5px; }
  .card { border-radius:14px; border:none; box-shadow:0 2px 10px rgba(0,0,0,.06); }
  .badge-risk { font-size:.9rem; padding:.4rem .7rem; border-radius:8px; color:#fff; }
  .action-item { border-left:6px solid; border-radius:8px; padding:10px 14px; margin-bottom:8px; background:#fff; }
  footer { color:#777; font-size:.85rem; padding:20px 0; text-align:center; }
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark" style="background:#2e7d32;">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('index') }}">🌱 AgroEdge</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav me-auto">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('index') }}">Crop Selection</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('dashboard') }}">Dashboard</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('disease') }}">Disease Detection</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('pest') }}">Pest Risk</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('weather') }}">Weather Risk</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('growth') }}">Growth Stage</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('report') }}">Report</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('history') }}">History</a></li>
      </ul>
    </div>
  </div>
</nav>
<div class="container py-4">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for m in messages %}
        <div class="alert alert-warning">{{ m }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
<footer>AgroEdge runs fully offline on local edge hardware — no data leaves this device.</footer>
</body>
</html>
"""


def render(body_html, **ctx):
    body = render_template_string(body_html, **ctx)
    return render_template_string(BASE_HTML, body=body)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        crop_key = request.form.get("crop_key")
        field_name = request.form.get("field_name", "").strip() or None
        if crop_key not in CROP_DATA:
            flash("Please select a valid crop.")
            return redirect(url_for("index"))
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO sessions_log (crop_key, field_name) VALUES (?, ?)",
            (crop_key, field_name),
        )
        conn.commit()
        session_id = cur.lastrowid
        conn.close()
        session.permanent = True
        session["session_id"] = session_id
        session["crop_key"] = crop_key
        session["field_name"] = field_name
        return redirect(url_for("dashboard"))

    body = """
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card p-4">
          <h3 class="mb-3">Select your crop</h3>
          <form method="post">
            <div class="mb-3">
              <label class="form-label">Crop</label>
              <select name="crop_key" class="form-select" required>
                {% for key, crop in crops.items() %}
                  <option value="{{ key }}">{{ crop.name }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label">Field / plot name (optional)</label>
              <input type="text" name="field_name" class="form-control" placeholder="e.g. North plot">
            </div>
            <button class="btn btn-success w-100">Start Monitoring</button>
          </form>
        </div>
      </div>
    </div>
    """
    return render(body, crops=CROP_DATA)


@app.route("/dashboard")
def dashboard():
    if "session_id" not in session:
        return redirect(url_for("index"))

    crop_key = session["crop_key"]
    session_id = session["session_id"]
    conn = get_db()
    disease_row = conn.execute("SELECT * FROM disease_records WHERE session_id=? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
    pest_row = conn.execute("SELECT * FROM pest_records WHERE session_id=? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
    weather_row = conn.execute("SELECT * FROM weather_records WHERE session_id=? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
    growth_row = conn.execute("SELECT * FROM growth_records WHERE session_id=? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
    conn.close()

    have_all = all([disease_row, pest_row, weather_row, growth_row])
    advice, actions, composite = [], [], None

    if have_all:
        disease_result = {"health_score": disease_row["health_score"], "risk_level": disease_row["risk_level"], "detected_disease": disease_row["detected_disease"], "treatment": ""}
        pest_result = {"pest_risk_score": pest_row["pest_risk_score"], "risk_level": pest_row["risk_level"], "predicted_pest": pest_row["predicted_pest"]}
        weather_result = {"weather_risk_score": weather_row["weather_risk_score"], "risk_level": weather_row["risk_level"], "dominant_risk": weather_row["dominant_risk"]}
        growth_result = {"stage_label": growth_row["detected_stage"], "stage_score": growth_row["stage_score"]}

        crop = CROP_DATA[crop_key]
        season = get_current_season()
        advice = [crop["seasonal_advisory"].get(season, "Continue standard seasonal care.")]
        if disease_result["risk_level"] in ("High", "Critical"):
            advice.append(f"Disease alert: {disease_result['detected_disease']} suspected.")
        if pest_result["risk_level"] in ("High", "Critical"):
            advice.append(f"Pest alert: monitor closely for {pest_result['predicted_pest']}.")
        if weather_result["risk_level"] in ("High", "Critical"):
            advice.append(f"Weather caution: elevated risk of {weather_result['dominant_risk'].lower()}.")
        advice.append(f"Growth stage: {growth_result['stage_label']} — tailor fertilizer and water accordingly.")

        composite = round(
            (disease_result["health_score"] * 0.5)
            + ((100 - pest_result["pest_risk_score"]) * 0.3)
            + ((100 - weather_result["weather_risk_score"]) * 0.2), 1
        )

        def urgency(level):
            return {"Critical": (4, "#c62828"), "High": (3, "#ef6c00"), "Medium": (2, "#f9a825"), "Low": (1, "#2e7d32")}[level]

        r, c = urgency(disease_result["risk_level"])
        actions.append({"title": f"Address {disease_result['detected_disease']}", "level": disease_result["risk_level"], "rank": r, "color": c})
        r, c = urgency(pest_result["risk_level"])
        actions.append({"title": f"Inspect for {pest_result['predicted_pest']}", "level": pest_result["risk_level"], "rank": r, "color": c})
        r, c = urgency(weather_result["risk_level"])
        actions.append({"title": f"Mitigate {weather_result['dominant_risk']}", "level": weather_result["risk_level"], "rank": r, "color": c})
        actions.sort(key=lambda a: a["rank"], reverse=True)

    body = """
    <h3>{{ crop.name }} Dashboard {% if field_name %}— {{ field_name }}{% endif %}</h3>
    {% if not have_all %}
      <div class="alert alert-info mt-3">
        Run <a href="{{ url_for('disease') }}">Disease Detection</a>,
        <a href="{{ url_for('pest') }}">Pest Risk</a>,
        <a href="{{ url_for('weather') }}">Weather Risk</a> and
        <a href="{{ url_for('growth') }}">Growth Stage</a> to populate today's advice.
      </div>
    {% else %}
      <div class="row mt-3">
        <div class="col-md-4">
          <div class="card p-3 text-center">
            <div class="text-muted">Crop Health Score</div>
            <div style="font-size:2.5rem; font-weight:700; color:#2e7d32;">{{ composite }}%</div>
          </div>
        </div>
        <div class="col-md-8">
          <div class="card p-3">
            <div class="text-muted mb-2">Daily AI Advice</div>
            <ul>
              {% for line in advice %}<li>{{ line }}</li>{% endfor %}
            </ul>
          </div>
        </div>
      </div>
      <div class="card p-3 mt-3">
        <div class="text-muted mb-2">Priority-Based Action List</div>
        {% for a in actions %}
          <div class="action-item" style="border-color:{{ a.color }};">
            <strong>{{ a.title }}</strong>
            <span class="badge-risk float-end" style="background:{{ a.color }};">{{ a.level }}</span>
          </div>
        {% endfor %}
      </div>
    {% endif %}
    """
    return render(body, crop=CROP_DATA[crop_key], field_name=session.get("field_name"),
                  have_all=have_all, advice=advice, actions=actions, composite=composite)


DISEASE_QUESTIONS = [
    ("affected_part", "Which part of the plant is most affected?",
     [("leaves", "Leaves"), ("stem_trunk", "Stem / Trunk"), ("roots", "Roots"), ("crown_bud", "Crown / Bud"), ("fruit_nut", "Fruit / Nut")]),
    ("discoloration", "What discoloration do you see?",
     [("none", "None"), ("yellowing", "Yellowing"), ("browning", "Browning"), ("blackening", "Blackening")]),
    ("odor_ooze", "Any foul smell or oozing from the plant?", [("yes", "Yes"), ("no", "No")]),
    ("onset_speed", "How quickly did symptoms appear?", [("sudden", "Suddenly (within days)"), ("gradual", "Gradually (over weeks)")]),
    ("spread", "Are the symptoms localized or spreading?", [("localized", "Localized"), ("spreading", "Spreading")]),
]

PEST_QUESTIONS = [
    ("visible_insects", "Have you seen insects on the plant?", [("yes", "Yes"), ("no", "No")]),
    ("damage_pattern", "What damage pattern is visible?",
     [("none", "None"), ("chewed_leaves", "Chewed leaves"), ("cut_marks", "Cut marks / holes"), ("wilting", "Wilting")]),
    ("sticky_residue", "Any sticky residue or sooty mould?", [("yes", "Yes"), ("no", "No")]),
    ("boring_holes", "Any boring holes or gum/frass exudation?", [("yes", "Yes"), ("no", "No")]),
    ("season_pressure", "Is current season known for high pest activity here?", [("high", "High"), ("low", "Low")]),
]

WEATHER_QUESTIONS = [
    ("rainfall", "Rainfall observed in the last few days?", [("none", "None"), ("light", "Light"), ("heavy", "Heavy")]),
    ("cloud_cover", "Current cloud cover?", [("clear", "Clear"), ("partly", "Partly cloudy"), ("overcast", "Overcast")]),
    ("wind", "Wind conditions?", [("calm", "Calm"), ("moderate", "Moderate"), ("strong", "Strong")]),
    ("temperature", "How does the temperature feel?", [("normal", "Normal"), ("hot", "Hot"), ("cold", "Cold")]),
    ("humidity", "Humidity level?", [("low", "Low"), ("normal", "Normal"), ("high", "High")]),
]

GROWTH_QUESTIONS = [
    ("height_category", "Plant height category?",
     [("very_small", "Very small"), ("small", "Small"), ("medium", "Medium"), ("tall", "Tall"), ("full_height", "Full height")]),
    ("leaf_condition", "Leaf condition?",
     [("few_leaves", "Few leaves"), ("moderate_leaves", "Moderate leaves"), ("dense_leaves", "Dense leaves"), ("thinning_leaves", "Thinning leaves")]),
    ("flowering_fruiting", "Flowering / fruiting status?",
     [("none", "None"), ("flowering", "Flowering"), ("fruiting", "Fruiting"), ("heavy_yield", "Heavy yield"), ("declining_yield", "Declining yield")]),
    ("trunk_girth", "Trunk / stem girth?",
     [("very_thin", "Very thin"), ("thin", "Thin"), ("moderate", "Moderate"), ("thick", "Thick"), ("very_thick", "Very thick")]),
    ("canopy_density", "Canopy density?", [("sparse", "Sparse"), ("developing", "Developing"), ("full", "Full"), ("very_full", "Very full")]),
]


def render_questionnaire(title, questions, image_optional, endpoint):
    body = """
    <div class="card p-4">
      <h3 class="mb-3">""" + title + """</h3>
      <form method="post" enctype="multipart/form-data">
        {% for key, label, options in questions %}
          <div class="mb-3">
            <label class="form-label">{{ label }}</label>
            <select name="{{ key }}" class="form-select" required>
              {% for val, text in options %}<option value="{{ val }}">{{ text }}</option>{% endfor %}
            </select>
          </div>
        {% endfor %}
        {% if image_optional %}
          <div class="mb-3">
            <label class="form-label">Upload a photo (optional, improves accuracy)</label>
            <input type="file" name="image" accept=".png,.jpg,.jpeg" class="form-control">
          </div>
        {% endif %}
        <button class="btn btn-success">Analyze</button>
      </form>
    </div>
    """
    return render(body, questions=questions, image_optional=image_optional)


@app.route("/disease", methods=["GET", "POST"])
def disease():
    if "session_id" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        answers = {k: request.form.get(k) for k, _, _ in DISEASE_QUESTIONS}
        image_path = save_upload(request.files.get("image"), "disease")
        result = analyze_disease(session["crop_key"], answers, image_path)

        conn = get_db()
        conn.execute(
            """INSERT INTO disease_records
               (session_id, crop_key, answers, image_path, detected_disease, health_score, risk_level)
               VALUES (?,?,?,?,?,?,?)""",
            (session["session_id"], session["crop_key"], json.dumps(answers), image_path,
             result["detected_disease"], result["health_score"], result["risk_level"]),
        )
        conn.commit()
        conn.close()

        body = """
        <div class="card p-4">
          <h3>Disease Detection Result</h3>
          <p>Crop Health Score: <strong>{{ r.health_score }}%</strong></p>
          <p>Risk Level: <span class="badge-risk" style="background:{{ r.color }};">{{ r.risk_level }}</span></p>
          <p>Likely condition: <strong>{{ r.detected_disease }}</strong></p>
          <p>Recommended action: {{ r.treatment }}</p>
          <a href="{{ url_for('dashboard') }}" class="btn btn-outline-success">Back to Dashboard</a>
        </div>
        """
        return render(body, r=result)

    return render_questionnaire("AI Crop Disease Detection", DISEASE_QUESTIONS, True, "disease")


@app.route("/pest", methods=["GET", "POST"])
def pest():
    if "session_id" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        answers = {k: request.form.get(k) for k, _, _ in PEST_QUESTIONS}
        result = predict_pest_risk(session["crop_key"], answers)

        conn = get_db()
        conn.execute(
            """INSERT INTO pest_records (session_id, crop_key, answers, predicted_pest, pest_risk_score, risk_level)
               VALUES (?,?,?,?,?,?)""",
            (session["session_id"], session["crop_key"], json.dumps(answers),
             result["predicted_pest"], result["pest_risk_score"], result["risk_level"]),
        )
        conn.commit()
        conn.close()

        body = """
        <div class="card p-4">
          <h3>Pest Risk Prediction</h3>
          <p>Pest Risk Score: <strong>{{ r.pest_risk_score }}%</strong></p>
          <p>Risk Level: <span class="badge-risk" style="background:{{ r.color }};">{{ r.risk_level }}</span></p>
          <p>Likely pest: <strong>{{ r.predicted_pest }}</strong></p>
          <a href="{{ url_for('dashboard') }}" class="btn btn-outline-success">Back to Dashboard</a>
        </div>
        """
        return render(body, r=result)

    return render_questionnaire("Pest Risk Predictor", PEST_QUESTIONS, False, "pest")


@app.route("/weather", methods=["GET", "POST"])
def weather():
    if "session_id" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        answers = {k: request.form.get(k) for k, _, _ in WEATHER_QUESTIONS}
        result = predict_weather_risk(answers)

        conn = get_db()
        conn.execute(
            """INSERT INTO weather_records (session_id, crop_key, answers, weather_risk_score, risk_level, dominant_risk)
               VALUES (?,?,?,?,?,?)""",
            (session["session_id"], session["crop_key"], json.dumps(answers),
             result["weather_risk_score"], result["risk_level"], result["dominant_risk"]),
        )
        conn.commit()
        conn.close()

        body = """
        <div class="card p-4">
          <h3>Offline Weather Risk Prediction</h3>
          <p>Weather Risk Score: <strong>{{ r.weather_risk_score }}%</strong></p>
          <p>Risk Level: <span class="badge-risk" style="background:{{ r.color }};">{{ r.risk_level }}</span></p>
          <p>Dominant concern: <strong>{{ r.dominant_risk }}</strong></p>
          <a href="{{ url_for('dashboard') }}" class="btn btn-outline-success">Back to Dashboard</a>
        </div>
        """
        return render(body, r=result)

    return render_questionnaire("Offline Weather Risk Predictor", WEATHER_QUESTIONS, False, "weather")


@app.route("/growth", methods=["GET", "POST"])
def growth():
    if "session_id" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        answers = {k: request.form.get(k) for k, _, _ in GROWTH_QUESTIONS}
        image_path = save_upload(request.files.get("image"), "growth")
        result = detect_growth_stage(session["crop_key"], answers, image_path)

        conn = get_db()
        conn.execute(
            """INSERT INTO growth_records (session_id, crop_key, answers, image_path, detected_stage, stage_score)
               VALUES (?,?,?,?,?,?)""",
            (session["session_id"], session["crop_key"], json.dumps(answers), image_path,
             result["stage_label"], result["stage_score"]),
        )
        conn.commit()
        conn.close()

        body = """
        <div class="card p-4">
          <h3>Growth Stage Detection</h3>
          <p>Maturity Score: <strong>{{ r.stage_score }}%</strong></p>
          <p>Detected Stage: <strong>{{ r.stage_label }}</strong></p>
          <a href="{{ url_for('dashboard') }}" class="btn btn-outline-success">Back to Dashboard</a>
        </div>
        """
        return render(body, r=result)

    return render_questionnaire("Growth Stage Detection", GROWTH_QUESTIONS, True, "growth")


@app.route("/report")
def report():
    # Defaults to the active session, but ?sid=<id> lets you open the
    # saved report for ANY past session pulled from /history.
    sid = request.args.get("sid", type=int) or session.get("session_id")
    if not sid:
        return redirect(url_for("index"))

    conn = get_db()
    session_row = conn.execute("SELECT * FROM sessions_log WHERE id=?", (sid,)).fetchone()
    if session_row is None:
        conn.close()
        flash("That session record no longer exists.")
        return redirect(url_for("history"))

    disease_rows = conn.execute("SELECT * FROM disease_records WHERE session_id=? ORDER BY id DESC", (sid,)).fetchall()
    pest_rows = conn.execute("SELECT * FROM pest_records WHERE session_id=? ORDER BY id DESC", (sid,)).fetchall()
    weather_rows = conn.execute("SELECT * FROM weather_records WHERE session_id=? ORDER BY id DESC", (sid,)).fetchall()
    growth_rows = conn.execute("SELECT * FROM growth_records WHERE session_id=? ORDER BY id DESC", (sid,)).fetchall()
    conn.close()

    crop = CROP_DATA.get(session_row["crop_key"])

    body = """
    <h3>History Report — {{ crop.name }}{% if session_row.field_name %} · {{ session_row.field_name }}{% endif %}</h3>
    <p class="text-muted">Session started {{ session_row.created_at }}</p>
    <div class="card p-3 mt-3">
      <h5>Disease Records</h5>
      <table class="table"><thead><tr><th>Date</th><th>Detected</th><th>Health Score</th><th>Risk</th></tr></thead><tbody>
      {% for d in disease_rows %}<tr><td>{{ d.created_at }}</td><td>{{ d.detected_disease }}</td><td>{{ d.health_score }}%</td><td>{{ d.risk_level }}</td></tr>{% endfor %}
      </tbody></table>
    </div>
    <div class="card p-3 mt-3">
      <h5>Pest Records</h5>
      <table class="table"><thead><tr><th>Date</th><th>Predicted Pest</th><th>Score</th><th>Risk</th></tr></thead><tbody>
      {% for p in pest_rows %}<tr><td>{{ p.created_at }}</td><td>{{ p.predicted_pest }}</td><td>{{ p.pest_risk_score }}%</td><td>{{ p.risk_level }}</td></tr>{% endfor %}
      </tbody></table>
    </div>
    <div class="card p-3 mt-3">
      <h5>Weather Records</h5>
      <table class="table"><thead><tr><th>Date</th><th>Dominant Risk</th><th>Score</th><th>Risk</th></tr></thead><tbody>
      {% for w in weather_rows %}<tr><td>{{ w.created_at }}</td><td>{{ w.dominant_risk }}</td><td>{{ w.weather_risk_score }}%</td><td>{{ w.risk_level }}</td></tr>{% endfor %}
      </tbody></table>
    </div>
    <div class="card p-3 mt-3">
      <h5>Growth Records</h5>
      <table class="table"><thead><tr><th>Date</th><th>Stage</th><th>Score</th></tr></thead><tbody>
      {% for g in growth_rows %}<tr><td>{{ g.created_at }}</td><td>{{ g.detected_stage }}</td><td>{{ g.stage_score }}%</td></tr>{% endfor %}
      </tbody></table>
    </div>
    <a href="{{ url_for('history') }}" class="btn btn-outline-success mt-2">← All Sessions</a>
    """
    return render(body, crop=crop, session_row=session_row, disease_rows=disease_rows,
                  pest_rows=pest_rows, weather_rows=weather_rows, growth_rows=growth_rows)


@app.route("/history")
def history():
    """Every monitoring session ever saved on this device, most recent first.
    Nothing is ever deleted from agroedge.db, so old data is always here —
    even after a browser restart or hitting Reset."""
    conn = get_db()
    sessions = conn.execute(
        "SELECT * FROM sessions_log ORDER BY id DESC"
    ).fetchall()
    conn.close()

    body = """
    <h3>All Monitoring Sessions</h3>
    <p class="text-muted">Every crop-selection session ever saved on this device.</p>
    <div class="card p-3 mt-3">
      <table class="table">
        <thead><tr><th>Date</th><th>Crop</th><th>Field</th><th></th></tr></thead>
        <tbody>
        {% for s in sessions %}
          <tr>
            <td>{{ s.created_at }}</td>
            <td>{{ crops[s.crop_key].name if s.crop_key in crops else s.crop_key }}</td>
            <td>{{ s.field_name or '—' }}</td>
            <td><a href="{{ url_for('report', sid=s.id) }}" class="btn btn-sm btn-outline-success">View Report</a></td>
          </tr>
        {% else %}
          <tr><td colspan="4">No sessions saved yet.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    """
    return render(body, sessions=sessions, crops=CROP_DATA)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
