"""Unit tests for DB isolation/rotation settings defaults."""

from config.settings import Settings


def test_settings_exposes_auto_rotation_fields():
    settings = Settings()

    assert isinstance(settings.auto_rotate_paper_db, bool)
    assert isinstance(settings.paper_db_archive_dir, str)
    assert settings.paper_db_archive_dir
