"""Tests for HTML dashboard generator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

VIEWER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIEWER_DIR))

from generate_dashboard import generate_dashboard, load_payload  # noqa: E402


@pytest.fixture
def sample_inventory(tmp_path: Path) -> Path:
    analysis = {
        "mode": "agent_platform",
        "model": "gemini-3.5-flash-lite",
        "project": "test-project",
        "results": [
            {
                "path": "/Users/example/projects",
                "size_bytes": 1024 * 1024 * 500,
                "size_human": "500M",
                "category": "user_custom",
                "confidence": 0.9,
                "reason_en": "User projects folder.",
                "reason_hu": "Felhasználói projektmappa.",
            },
            {
                "path": "/Users/example/Library/Caches/Foo",
                "size_bytes": 1024 * 1024 * 200,
                "size_human": "200M",
                "category": "cache_or_temp",
                "confidence": 0.95,
                "reason_en": "Application cache.",
                "reason_hu": "Alkalmazás cache.",
            },
        ],
    }
    plan = {
        "counts": {"copy": 1, "app": 0, "skip": 1, "review": 0},
        "sections": {
            "copy": [analysis["results"][0]],
            "app_data": [],
            "skip": [analysis["results"][1]],
            "review": [],
        },
    }
    (tmp_path / "analysis-report.json").write_text(
        json.dumps(analysis), encoding="utf-8"
    )
    (tmp_path / "migration-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "collector-output.json").write_text(
        json.dumps({"generated_at": "2026-01-01", "folder_count": 2, "max_depth": 3}),
        encoding="utf-8",
    )
    (tmp_path / "00-INDEX.md").write_text("# Index", encoding="utf-8")
    return tmp_path


def test_load_payload(sample_inventory: Path):
    payload = load_payload(sample_inventory)
    assert payload["analysis"]["mode"] == "agent_platform"
    assert payload["plan"]["counts"]["copy"] == 1
    assert payload["collector"]["folder_count"] == 2
    assert "00-INDEX.md" in payload["inventory_files"]


def test_generate_dashboard(sample_inventory: Path, tmp_path: Path):
    out = tmp_path / "dashboard.html"
    generate_dashboard(sample_inventory, out)
    html = out.read_text(encoding="utf-8")
    assert "<title>mac-migration dashboard</title>" in html
    assert "/Users/example/projects" in html
    assert "mac-migration-checklist-v1" in html


def test_missing_analysis(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="analysis JSON"):
        load_payload(tmp_path)
