"""Tests for audio device capture."""

from __future__ import annotations

import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from capture_audio_devices import build_restore_hints, parse_audio_text  # noqa: E402


def test_parse_audio_text_blackhole():
    raw = """
Audio:

    Devices:

        BlackHole 16ch:

          Input Channels: 16
          Manufacturer: Existential Audio Inc.
          Output Channels: 16
          Current SampleRate: 44100
          Transport: Virtual
"""
    devices = parse_audio_text(raw)
    assert len(devices) == 1
    assert devices[0]["name"] == "BlackHole 16ch"
    assert devices[0]["transport"] == "Virtual"


def test_blackhole_restore_hint():
    hints = build_restore_hints(
        [{"name": "BlackHole 16ch", "transport": "Virtual"}],
        [{"name": "BlackHole16ch", "is_blackhole": True, "bundle": "BlackHole16ch.driver"}],
        ["blackhole-16ch"],
    )
    assert any(h["product"] == "BlackHole" for h in hints)
    assert "blackhole-16ch" in hints[0]["install_command"]
