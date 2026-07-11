"""
utils/image_processing.py
---------------------------
Handles the optional plant-photo uploads used by disease detection and
growth stage detection. Includes a lightweight, fully-offline visual
heuristic (no cloud CV model, no network call) that estimates plant
stress from color composition — a supplement to the farmer's answers,
never a replacement for them.
"""

import os
from datetime import datetime

from werkzeug.utils import secure_filename

from config import Config

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def allowed_file(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS
    )


def save_upload(file_storage, prefix):
    """
    Saves an uploaded image to static/uploads/ with a collision-safe
    filename. Returns the saved path, or None if no valid file was
    provided (uploads are optional throughout AgroEdge).
    """
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    timestamp = int(datetime.now().timestamp())
    filename = secure_filename(f"{prefix}_{timestamp}_{file_storage.filename}")
    path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file_storage.save(path)
    return path


def analyze_image_heuristic(filepath, thumbnail_size=(200, 200)):
    """
    Estimates the proportion of unhealthy (brown/yellow) vs healthy
    (green) pixels in an uploaded plant photo. Returns a 0-100 "stress
    score", or None if Pillow isn't installed or the file can't be read.

    This runs entirely on-device with no external calls — it is a
    coarse color-composition heuristic, not a trained disease classifier,
    and is only ever used to nudge the questionnaire-based score in
    ai/disease_detector.py and ai/growth_stage.py.
    """
    if not PIL_AVAILABLE or not filepath or not os.path.exists(filepath):
        return None

    try:
        img = Image.open(filepath).convert("RGB")
        img.thumbnail(thumbnail_size)
        pixels = list(img.getdata())
        if not pixels:
            return None

        unhealthy = 0
        for r, g, b in pixels:
            if g > r and g > b and g > 60:
                continue  # healthy green
            if r > 90 and g > 60 and b < 90:
                unhealthy += 1  # brown / yellow / dry tones

        return round((unhealthy / len(pixels)) * 100, 1)
    except Exception:
        return None


def delete_upload(filepath):
    """Best-effort cleanup helper; never raises."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            return True
    except OSError:
        pass
    return False