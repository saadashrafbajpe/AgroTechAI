"""
utils/helpers.py
------------------
General-purpose helpers shared across routes/ and ai/: current season
detection, loading the preloaded offline crop knowledge base, and
mapping a numeric score onto a crop's growth-stage bands.
"""

import json
import os
from datetime import datetime

from config import Config
from utils.calculations import score_to_band

_crop_data_cache = {}


def get_current_season():
    """
    India-general seasonal bucket by month, used by season_advisory
    and advice_engine when the farmer doesn't override it:
        summer       -> Mar, Apr, May
        monsoon      -> Jun, Jul, Aug, Sep
        post_monsoon -> Oct, Nov
        winter       -> Dec, Jan, Feb
    """
    month = datetime.now().month
    if month in (3, 4, 5):
        return "summer"
    if month in (6, 7, 8, 9):
        return "monsoon"
    if month in (10, 11):
        return "post_monsoon"
    return "winter"


def load_crop_data(crop_key, use_cache=True):
    """
    Loads a crop's offline knowledge base from crop_data/<crop_key>.json.
    Results are cached in-process since the file never changes at runtime
    on the edge device.
    """
    if use_cache and crop_key in _crop_data_cache:
        return _crop_data_cache[crop_key]

    path = os.path.join(Config.CROP_DATA_DIR, f"{crop_key}.json")
    if not os.path.exists(path):
        raise ValueError(f"Unknown crop: {crop_key}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if use_cache:
        _crop_data_cache[crop_key] = data
    return data


def list_supported_crops():
    """Returns {crop_key: display_name} for every crop with a data file,
    restricted to the crops declared in Config.SUPPORTED_CROPS."""
    crops = {}
    for crop_key in Config.SUPPORTED_CROPS:
        try:
            crops[crop_key] = load_crop_data(crop_key)["name"]
        except ValueError:
            continue
    return crops


def score_to_stage(score, growth_stages):
    """Maps a 0-100 growth score onto a crop's defined stage bands
    (each stage dict uses "min"/"max" keys, per crop_data/*.json)."""
    bands = [{"min": s["min"], "max": s["max"], **s} for s in growth_stages]
    return score_to_band(score, bands, default=growth_stages[-1] if growth_stages else None)


def format_timestamp(dt=None):
    """Consistent local timestamp formatting for logs and records."""
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")
