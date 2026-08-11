"""Tests for restore engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESTORER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESTORER_DIR))

from restore import restore_aliases  # noqa: E402


def test_restore_aliases_dry_run(tmp_path: Path):
    inv = tmp_path / "inventory"
    inv.mkdir()
    (inv / "environment-snapshot.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "aliases": {
                    "count": 1,
                    "items": [
                        {
                            "name": "k",
                            "definition": "kubectl",
                            "raw": "alias k='kubectl'",
                            "source_file": ".zshrc",
                            "line": 1,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    result = restore_aliases(inv, dry_run=True)
    assert result["applied"] == 1
    assert result["dry_run"] is True
    assert "source" in result["source_line"]
