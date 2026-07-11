"""
utils/validators.py
---------------------
Input validation for the questionnaire forms and image uploads used
throughout AgroEdge. Keeping this separate from the routes lets every
Blueprint apply the same rules consistently.
"""

import os
from config import Config


def validate_crop_key(crop_key):
    """Returns (is_valid, error_message)."""
    if not crop_key:
        return False, "Please select a crop."
    if crop_key not in Config.SUPPORTED_CROPS:
        return False, f"'{crop_key}' is not a supported crop."
    return True, None


def validate_field_name(field_name, max_length=80):
    """Trims and caps the optional field/plot name. Always valid — just cleaned."""
    if not field_name:
        return None
    cleaned = field_name.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned or None


def validate_answers(answers, required_keys):
    """
    Confirms every required question has a non-empty answer.
    Returns (is_valid, missing_keys).
    """
    missing = [key for key in required_keys if not answers.get(key)]
    return (len(missing) == 0), missing


def validate_choice(value, allowed_values, field_label="field"):
    """Confirms a submitted value is one of the options actually offered
    in the form, guarding against tampered requests."""
    if value not in allowed_values:
        return False, f"Invalid value submitted for {field_label}."
    return True, None


def validate_image_file(file_storage):
    """
    Validates an (optional) uploaded plant photo.
    Returns (is_valid, error_message). A missing file is considered
    valid, since photos are optional throughout AgroEdge — callers
    should check `file_storage` truthiness first if they need to
    distinguish "no file" from "valid file".
    """
    if file_storage is None or file_storage.filename == "":
        return True, None

    filename = file_storage.filename
    if "." not in filename:
        return False, "Uploaded file has no extension."

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in Config.ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(Config.ALLOWED_IMAGE_EXTENSIONS))
        return False, f"Unsupported image type '.{ext}'. Allowed: {allowed}."

    # Best-effort size check; some WSGI servers don't populate content_length
    # until the stream is read, so this is a soft check, not the only one.
    size = getattr(file_storage, "content_length", None)
    if size and size > Config.MAX_CONTENT_LENGTH:
        max_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)
        return False, f"Image exceeds the {max_mb}MB upload limit."

    return True, None


def validate_session_active(session):
    """Confirms a Flask session has an active crop-monitoring session."""
    if "crop_key" not in session:
        return False, "No active crop selected. Please start from the beginning."
    return True, None