import json
import os
from typing import Any, Dict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SETTINGS_PATH = os.path.join(REPO_ROOT, "configs", "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "appVersion": "1.0",
    "defaultOutputPath": "",
    "openFolderAfterProcessing": True,
    "lastZipOnly": False,
    "lastIndividualPdfs": False,
    "lastInputDir": ""
}


def load_settings() -> Dict[str, Any]:
    """
    Loads settings from configs/settings.json.
    If file is missing or invalid, returns DEFAULT_SETTINGS.
    """
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update(data)
    return merged


def save_settings(settings: Dict[str, Any]) -> None:
    """
    Saves settings to configs/settings.json.
    """
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)