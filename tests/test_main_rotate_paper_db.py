"""Unit tests for paper DB rotation command."""

from pathlib import Path

from config.settings import Settings
from src.cli.runtime import cmd_rotate_paper_db


def test_rotate_paper_db_moves_file(tmp_path):
    source = tmp_path / "trading_paper.db"
    source.write_text("paper-data", encoding="utf-8")
    archive_dir = tmp_path / "archive"

    settings = Settings()
    settings.db_url_paper = f"sqlite:///{source.as_posix()}"
    settings.db_url_live = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
    settings.db_url_test = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"

    result = cmd_rotate_paper_db(
        settings,
        archive_dir=str(archive_dir),
        keep_original=False,
        suffix="20260223_120000",
    )

    archived = archive_dir / "trading_paper_20260223_120000.db"
    assert result["rotated"] is True
    assert not source.exists()
    assert archived.exists()
    assert archived.read_text(encoding="utf-8") == "paper-data"


def test_rotate_paper_db_copies_when_keep_original(tmp_path):
    source = tmp_path / "trading_paper.db"
    source.write_text("paper-data", encoding="utf-8")
    archive_dir = tmp_path / "archive"

    settings = Settings()
    settings.db_url_paper = f"sqlite:///{source.as_posix()}"
    settings.db_url_live = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
    settings.db_url_test = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"

    result = cmd_rotate_paper_db(
        settings,
        archive_dir=str(archive_dir),
        keep_original=True,
        suffix="20260223_120001",
    )

    archived = archive_dir / "trading_paper_20260223_120001.db"
    assert result["rotated"] is True
    assert source.exists()
    assert archived.exists()


def test_rotate_paper_db_noop_when_missing(tmp_path):
    source = tmp_path / "missing_paper.db"
    archive_dir = tmp_path / "archive"

    settings = Settings()
    settings.db_url_paper = f"sqlite:///{source.as_posix()}"
    settings.db_url_live = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
    settings.db_url_test = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"

    result = cmd_rotate_paper_db(settings, archive_dir=str(archive_dir), keep_original=False)

    assert result["rotated"] is False
    assert result["archive"] is None
