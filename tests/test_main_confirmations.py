"""Tests for explicit runtime confirmation gates in CLI helper logic."""

import pytest

from src.cli.runtime import _require_explicit_confirmation


def test_paper_trial_confirmation_missing_raises(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _require_explicit_confirmation("paper_trial")

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "--confirm-paper-trial" in captured.out


def test_paper_trial_confirmation_present_passes():
    _require_explicit_confirmation("paper_trial", confirm_paper_trial=True)


def test_paper_confirmation_missing_raises(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _require_explicit_confirmation("paper")

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "--confirm-paper" in captured.out


def test_live_confirmation_missing_raises(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _require_explicit_confirmation("live")

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "--confirm-live" in captured.out
