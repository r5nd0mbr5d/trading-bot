"""Unit tests for runtime DB isolation resolution."""

import pytest

from config.settings import Settings
from src.cli.runtime import resolve_runtime_db_path


def test_resolve_runtime_db_path_uses_mode_specific_urls():
    settings = Settings()
    settings.db_url_paper = "sqlite:///paper_mode.db"
    settings.db_url_live = "sqlite:///live_mode.db"
    settings.db_url_test = "sqlite:///test_mode.db"
    settings.strict_db_isolation = True

    assert resolve_runtime_db_path(settings, "paper") == "paper_mode.db"
    assert resolve_runtime_db_path(settings, "live") == "live_mode.db"
    assert resolve_runtime_db_path(settings, "test") == "test_mode.db"


def test_resolve_runtime_db_path_honors_explicit_override():
    settings = Settings()
    assert resolve_runtime_db_path(settings, "paper", explicit_db_path="custom.db") == "custom.db"


def test_resolve_runtime_db_path_raises_when_isolation_not_distinct():
    settings = Settings()
    settings.db_url_paper = "sqlite:///same.db"
    settings.db_url_live = "sqlite:///same.db"
    settings.db_url_test = "sqlite:///test.db"
    settings.strict_db_isolation = True

    with pytest.raises(RuntimeError):
        resolve_runtime_db_path(settings, "paper")
