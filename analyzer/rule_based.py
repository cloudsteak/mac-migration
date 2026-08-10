"""Rule-based folder categorization fallback (no Agent Platform)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

CATEGORIES = ("app_data", "user_custom", "cache_or_temp", "uncertain")

CACHE_PATTERNS = (
    r"/Caches(/|$)",
    r"/\.Trash(/|$)",
    r"/tmp(/|$)",
    r"/Temp(/|$)",
    r"/Logs(/|$)",
    r"/log(/|$)",
    r"/\.npm/_cacache",
    r"/\.cache(/|$)",
    r"/DerivedData(/|$)",
    r"/\.gradle/caches",
    r"/\.m2/repository",
)

APP_DATA_PATTERNS = (
    r"/Library/Application Support/",
    r"/Library/Containers/",
    r"/Library/Group Containers/",
    r"/Library/Preferences/",
    r"/Library/Saved Application State/",
    r"/\.vscode/extensions/",
    r"/\.cursor/extensions/",
    r"/node_modules(/|$)",
)

USER_CUSTOM_PATTERNS = (
    r"/Documents/",
    r"/Desktop/",
    r"/Downloads/",
    r"/Music/",
    r"/Movies/",
    r"/Pictures/",
    r"/Projects/",
    r"/dev/",
    r"/Development/",
    r"sample",
    r"export",
    r"project",
    r"preset",
    r"library",
)

REASONS = {
    "cache": {
        "en": "Rule: path matches cache/temp pattern.",
        "hu": "Szabály: cache/ideiglenes minta illeszkedik.",
    },
    "app_data": {
        "en": "Rule: path matches application data location.",
        "hu": "Szabály: alkalmazás-adat hely illeszkedik.",
    },
    "user_custom": {
        "en": "Rule: path matches user content location.",
        "hu": "Szabály: felhasználói tartalom hely illeszkedik.",
    },
    "uncertain": {
        "en": "Rule: no confident match — manual review recommended.",
        "hu": "Szabály: nincs biztos illeszkés — kézi ellenőrzés javasolt.",
    },
}


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, path, re.IGNORECASE) for p in patterns)


def _result(path: str, category: str, confidence: float, reason_key: str) -> dict:
    reasons = REASONS[reason_key]
    return {
        "path": path,
        "category": category,
        "confidence": confidence,
        "reason_en": reasons["en"],
        "reason_hu": reasons["hu"],
    }


def categorize_folder(folder: dict) -> dict:
    path = folder.get("path", "")

    if _matches(path, CACHE_PATTERNS):
        return _result(path, "cache_or_temp", 0.85, "cache")

    if _matches(path, USER_CUSTOM_PATTERNS):
        base = PurePosixPath(path).name.lower()
        if base in {"application support", "containers", "preferences"}:
            return _result(path, "app_data", 0.7, "app_data")
        return _result(path, "user_custom", 0.75, "user_custom")

    if _matches(path, APP_DATA_PATTERNS):
        return _result(path, "app_data", 0.8, "app_data")

    return _result(path, "uncertain", 0.4, "uncertain")


def analyze_folders(folders: list[dict]) -> list[dict]:
    return [categorize_folder(f) for f in folders]


def reason_for_lang(result: dict, lang: str) -> str:
    if lang == "hu":
        return result.get("reason_hu") or result.get("reason_en", "")
    return result.get("reason_en") or result.get("reason_hu", "")
