"""
AgroEdge configuration.
Centralizes all paths and settings so the app stays fully offline,
edge-friendly, and consistent with the project's folder structure:

AgroEdge/
├── app.py
├── config.py
├── database/
│   └── agroedge.db
├── models/
├── static/
│   └── uploads/
├── crop_data/
└── logs/
"""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))



class Config:
    # --- Core / security ---
    SECRET_KEY = os.environ.get("AGROEDGE_SECRET_KEY", "agroedge-offline-edge-key")
    DEBUG = os.environ.get("AGROEDGE_DEBUG", "true").lower() == "true"

    # --- Server ---
    HOST = os.environ.get("AGROEDGE_HOST", "127.0.0.1")
    PORT = int(os.environ.get("AGROEDGE_PORT", 5000))

    # --- Paths ---
    DATABASE_DIR = os.path.join(BASE_DIR, "database")
    DATABASE_PATH = os.path.join(DATABASE_DIR, "agroedge.db")

    MODELS_DIR = os.path.join(BASE_DIR, "models")

    STATIC_DIR = os.path.join(BASE_DIR, "static")
    UPLOAD_FOLDER = os.path.join(STATIC_DIR, "uploads")

    CROP_DATA_DIR = os.path.join(BASE_DIR, "crop_data")

    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")

    # --- Uploads ---
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB — keeps things light for edge hardware

    # --- Domain ---
    SUPPORTED_CROPS = ["coconut", "arecanut", "rice", "rubber", "cashew"]

    # Risk Meter thresholds (0-100 scale) shared by disease, pest, and weather modules
    RISK_THRESHOLDS = {
        "low": (0, 25),
        "medium": (25, 50),
        "high": (50, 75),
        "critical": (75, 100),
    }
    RISK_COLORS = {
        "Low": "#2e7d32",
        "Medium": "#f9a825",
        "High": "#ef6c00",
        "Critical": "#c62828",
    }

    # Crop Health Score weighting (disease / pest / weather components)
    HEALTH_SCORE_WEIGHTS = {
        "disease": 0.5,
        "pest": 0.3,
        "weather": 0.2,
    }

    @staticmethod
    def ensure_directories():
        """Creates every directory this config points to, if missing.
        Safe to call on every startup — matches the offline, zero-setup
        requirement for edge deployment."""
        for path in [
            Config.DATABASE_DIR,
            Config.MODELS_DIR,
            Config.STATIC_DIR,
            Config.UPLOAD_FOLDER,
            Config.CROP_DATA_DIR,
            Config.LOG_DIR,
        ]:
            os.makedirs(path, exist_ok=True)

