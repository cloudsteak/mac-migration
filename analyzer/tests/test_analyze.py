"""Tests for analyzer logic (no live Agent Platform calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from analyze import (  # noqa: E402
    chunk,
    filter_folders,
    parse_model_response,
    strip_json_fence,
)
from paths import hu_path  # noqa: E402
from rule_based import categorize_folder  # noqa: E402


@pytest.fixture
def sample_folders():
    return [
        {"path": "/Users/example/Library/Caches/Foo", "size_bytes": 200_000_000},
        {"path": "/Users/example/Documents/projects", "size_bytes": 150_000_000},
        {"path": "/Users/example/random", "size_bytes": 50_000_000},
    ]


def test_filter_folders_min_size(sample_folders):
    filtered = filter_folders(sample_folders, 100 * 1024 * 1024)
    assert len(filtered) == 2
    paths = {f["path"] for f in filtered}
    assert "/Users/example/random" not in paths


def test_chunk():
    items = list(range(7))
    batches = list(chunk(items, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6]]


def test_strip_json_fence():
    raw = '```json\n[{"path": "/a"}]\n```'
    assert strip_json_fence(raw) == '[{"path": "/a"}]'


def test_hu_path():
    assert hu_path(Path("analysis-report.md")) == Path("analysis-report_HU.md")


def test_parse_model_response_bilingual():
    batch = [{"path": "/a"}, {"path": "/b"}]
    raw = json.dumps(
        [
            {
                "path": "/a",
                "category": "user_custom",
                "confidence": 0.9,
                "reason_en": "User docs",
                "reason_hu": "Felhasználói doksi",
            },
            {
                "path": "/b",
                "category": "cache_or_temp",
                "confidence": 0.8,
                "reason_en": "Cache",
                "reason_hu": "Gyorsítótár",
            },
        ]
    )
    results = parse_model_response(raw, batch)
    assert results[0]["reason_en"] == "User docs"
    assert results[0]["reason_hu"] == "Felhasználói doksi"
    assert results[1]["category"] == "cache_or_temp"


def test_parse_model_response_missing_path():
    batch = [{"path": "/missing"}]
    raw = json.dumps([])
    results = parse_model_response(raw, batch)
    assert results[0]["category"] == "uncertain"
    assert results[0]["reason_en"]
    assert results[0]["reason_hu"]


def test_rule_based_cache():
    folder = {"path": "/Users/example/Library/Caches/com.app/Data"}
    result = categorize_folder(folder)
    assert result["category"] == "cache_or_temp"
    assert result["reason_en"]
    assert result["reason_hu"]


def test_rule_based_user_custom():
    folder = {"path": "/Users/example/Documents/vegleges-export"}
    result = categorize_folder(folder)
    assert result["category"] == "user_custom"
