"""Tests for assistant tool client-id and endpoint policy helpers."""

import pytest

from src.execution.assistant_tool_policy import endpoint_profile_tag
from src.execution.assistant_tool_policy import validate_non_overlapping_bands
from src.execution.assistant_tool_policy import validate_probe_range


def test_validate_non_overlapping_bands_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="overlaps runtime range"):
        validate_non_overlapping_bands(1, 499, 450, 600)


def test_validate_probe_range_rejects_sequence_overflow() -> None:
    with pytest.raises(ValueError, match="exceeds assistant range"):
        validate_probe_range(
            initial_client_id=5098,
            attempts=3,
            step=1,
            assistant_start=5000,
            assistant_end=5099,
        )


def test_endpoint_profile_tag_uses_mode_from_port() -> None:
    assert (
        endpoint_profile_tag("uk_paper", "127.0.0.1", 7497) == "ibkr:uk_paper:paper:127.0.0.1:7497"
    )
    assert endpoint_profile_tag("default", "localhost", 7496) == "ibkr:default:live:localhost:7496"
