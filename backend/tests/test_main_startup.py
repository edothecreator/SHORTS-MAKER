"""Unit tests for the startup config loader in ``backend.main``.

Covers Requirements 12.6, 12.13, and 2.6.
"""
from __future__ import annotations

import importlib
import sys
from typing import Mapping

import pytest

# Importing ``backend.main`` runs its bootstrap, which requires the env vars to
# be present. We pre-populate them before the first import; individual tests
# that need to test bootstrap behavior under different conditions reload the
# module manually with ``importlib.reload``.


@pytest.fixture(autouse=True)
def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "base")


@pytest.fixture
def main_module():
    if "backend.main" in sys.modules:
        return importlib.reload(sys.modules["backend.main"])
    return importlib.import_module("backend.main")


# ---------------------------------------------------------------------------
# resolve_whisper_model_size (Requirement 2.6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["tiny", "base", "small", "medium", "large"],
)
def test_resolve_whisper_model_size_accepts_allowed_values(main_module, value):
    effective, warning = main_module.resolve_whisper_model_size(value)
    assert effective == value
    assert warning is None


@pytest.mark.parametrize("value", ["TINY", "Base", "  small  "])
def test_resolve_whisper_model_size_normalizes_case_and_whitespace(main_module, value):
    effective, warning = main_module.resolve_whisper_model_size(value)
    assert effective == value.strip().lower()
    assert warning is None


@pytest.mark.parametrize("value", ["xl", "huge", "tiny.en", "BASE-multi"])
def test_resolve_whisper_model_size_falls_back_with_warning(main_module, value):
    effective, warning = main_module.resolve_whisper_model_size(value)
    assert effective == main_module.DEFAULT_WHISPER_MODEL_SIZE
    assert warning is not None
    assert value in warning
    assert main_module.DEFAULT_WHISPER_MODEL_SIZE in warning


# ---------------------------------------------------------------------------
# load_startup_config (Requirement 12.13)
# ---------------------------------------------------------------------------


def test_load_startup_config_returns_validated_values(main_module):
    env: Mapping[str, str] = {
        "GOOGLE_API_KEY": "  abc123  ",
        "WHISPER_MODEL_SIZE": "small",
    }
    cfg = main_module.load_startup_config(env)
    # Trimmed.
    assert cfg["google_api_key"] == "abc123"
    assert cfg["whisper_model_size"] == "small"
    assert cfg["whisper_warning"] is None


def test_load_startup_config_records_whisper_warning(main_module):
    env = {"GOOGLE_API_KEY": "abc", "WHISPER_MODEL_SIZE": "ultra"}
    cfg = main_module.load_startup_config(env)
    assert cfg["whisper_model_size"] == "base"
    assert cfg["whisper_warning"] is not None
    assert "ultra" in str(cfg["whisper_warning"])


@pytest.mark.parametrize(
    "env",
    [
        {"WHISPER_MODEL_SIZE": "base"},  # missing GOOGLE_API_KEY
        {"GOOGLE_API_KEY": "", "WHISPER_MODEL_SIZE": "base"},
        {"GOOGLE_API_KEY": "   ", "WHISPER_MODEL_SIZE": "base"},
    ],
)
def test_load_startup_config_rejects_missing_or_empty_google_api_key(main_module, env):
    with pytest.raises(main_module.StartupConfigError) as exc_info:
        main_module.load_startup_config(env)
    assert "GOOGLE_API_KEY" in str(exc_info.value)


@pytest.mark.parametrize(
    "env",
    [
        {"GOOGLE_API_KEY": "abc"},  # missing WHISPER_MODEL_SIZE
        {"GOOGLE_API_KEY": "abc", "WHISPER_MODEL_SIZE": ""},
        {"GOOGLE_API_KEY": "abc", "WHISPER_MODEL_SIZE": "\t \n"},
    ],
)
def test_load_startup_config_rejects_missing_or_empty_whisper_model_size(
    main_module, env,
):
    with pytest.raises(main_module.StartupConfigError) as exc_info:
        main_module.load_startup_config(env)
    assert "WHISPER_MODEL_SIZE" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Module bootstrap (Requirements 12.6, 12.13, 2.6)
# ---------------------------------------------------------------------------


def test_module_bootstrap_exposes_validated_constants(main_module):
    assert main_module.GOOGLE_API_KEY == "test-key"
    assert main_module.WHISPER_MODEL_SIZE == "base"
    assert main_module.WHISPER_MODEL_WARNING is None


def test_module_bootstrap_aborts_when_required_key_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "base")
    # ``backend.main`` already imported in this session; reload to re-run
    # bootstrap under the modified environment.
    sys.modules.pop("backend.main", None)
    with pytest.raises(Exception) as exc_info:
        importlib.import_module("backend.main")
    assert "GOOGLE_API_KEY" in str(exc_info.value)


def test_module_bootstrap_records_whisper_warning(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "huge")
    sys.modules.pop("backend.main", None)
    module = importlib.import_module("backend.main")
    assert module.WHISPER_MODEL_SIZE == "base"
    assert module.WHISPER_MODEL_WARNING is not None
    assert "huge" in module.WHISPER_MODEL_WARNING
