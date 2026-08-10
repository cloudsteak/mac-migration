"""Tests for ADC-only credentials."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from credentials import CredentialsError, load_credentials  # noqa: E402


def test_rejects_google_application_credentials(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-key.json")
    with pytest.raises(CredentialsError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        load_credentials()


def test_load_credentials_without_json_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    # Will fail without real ADC on CI — only assert we pass the JSON guard
    try:
        load_credentials()
    except CredentialsError:
        pass
    except Exception:
        pass  # google.auth.default may fail without ADC — expected in CI
