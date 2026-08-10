"""Tests for GCP setup helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from gcp_setup import VERTEX_AI_API, _service_state, ensure_api_enabled  # noqa: E402


def test_vertex_ai_api_constant():
    assert VERTEX_AI_API == "aiplatform.googleapis.com"


@patch("gcp_setup._request_json")
def test_service_state_enabled(mock_request):
    mock_request.return_value = {"state": "ENABLED"}
    assert _service_state("proj", VERTEX_AI_API, "token") == "ENABLED"


@patch("gcp_setup.get_access_token", return_value="token")
@patch("gcp_setup._service_state", return_value="ENABLED")
def test_ensure_api_enabled_skips_when_already_on(_state, _token):
    ensure_api_enabled("my-project")


@patch("gcp_setup.get_access_token", return_value="token")
@patch("gcp_setup._enable_service")
@patch("gcp_setup._service_state", return_value=None)
def test_ensure_api_enabled_calls_enable(_state, mock_enable, _token):
    ensure_api_enabled("my-project")
    mock_enable.assert_called_once_with("my-project", VERTEX_AI_API, "token")


@patch("gcp_setup.load_credentials")
def test_check_prerequisites_adc_ok(mock_load):
    from gcp_setup import check_prerequisites

    check_prerequisites("proj")
    mock_load.assert_called_once()
