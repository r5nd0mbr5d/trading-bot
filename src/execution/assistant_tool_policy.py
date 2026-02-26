"""Client-id and endpoint policy helpers for assistant/integration tools."""

from __future__ import annotations


def ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Return ``True`` when inclusive ranges overlap."""
    return start_a <= end_b and start_b <= end_a


def validate_non_overlapping_bands(
    runtime_start: int,
    runtime_end: int,
    assistant_start: int,
    assistant_end: int,
) -> None:
    """Validate runtime and assistant client-id bands are non-overlapping."""
    if runtime_start > runtime_end:
        raise ValueError("runtime_start must be <= runtime_end")
    if assistant_start > assistant_end:
        raise ValueError("assistant_start must be <= assistant_end")
    if ranges_overlap(runtime_start, runtime_end, assistant_start, assistant_end):
        raise ValueError("assistant client-id range overlaps runtime range")


def validate_probe_range(
    initial_client_id: int,
    attempts: int,
    step: int,
    assistant_start: int,
    assistant_end: int,
) -> None:
    """Validate assistant probe sequence stays inside assistant band."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if step < 1:
        raise ValueError("step must be >= 1")
    if initial_client_id < assistant_start or initial_client_id > assistant_end:
        raise ValueError("initial client id outside assistant range")
    final_client_id = initial_client_id + (attempts - 1) * step
    if final_client_id > assistant_end:
        raise ValueError("probe sequence exceeds assistant range")


def endpoint_profile_tag(profile: str, host: str, port: int) -> str:
    """Build deterministic endpoint profile tag for status outputs."""
    mode = "custom"
    if int(port) == 7497:
        mode = "paper"
    elif int(port) == 7496:
        mode = "live"
    return f"ibkr:{profile}:{mode}:{host}:{int(port)}"
