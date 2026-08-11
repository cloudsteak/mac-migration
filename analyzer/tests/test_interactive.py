"""Tests for interactive migration review."""

from __future__ import annotations

import sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from interactive import decision_to_folder_results, strip_json_fence  # noqa: E402


def test_strip_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert strip_json_fence(raw) == '{"a": 1}'


def test_decision_to_folder_results():
    data = {
        "decisions": {
            "dot:.pyenv": {
                "decision": "migrate",
                "component_id": "dot:.pyenv",
                "component_name": ".pyenv",
                "analysis": {
                    "migration_guidance_en": "Copy pyenv versions.",
                    "migration_guidance_hu": "Másold a pyenv verziókat.",
                    "confidence": 0.9,
                },
                "related_folders": [
                    {
                        "path": "/Users/x/.pyenv",
                        "size_human": "2G",
                        "size_bytes": 2_000_000_000,
                    }
                ],
            },
            "app:Foo.app": {
                "decision": "skip",
                "component_id": "app:Foo.app",
                "paths": ["/Applications/Foo.app"],
                "analysis": {"migration_guidance_en": "Not needed."},
                "related_folders": [],
            },
        }
    }
    results = decision_to_folder_results(data)
    assert len(results) == 2
    migrate = next(r for r in results if r["path"] == "/Users/x/.pyenv")
    assert migrate["category"] == "user_custom"
    assert migrate["interactive_decision"] == "migrate"
    skip = next(r for r in results if r["path"] == "/Applications/Foo.app")
    assert skip["category"] == "cache_or_temp"
