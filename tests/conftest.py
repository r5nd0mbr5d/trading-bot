"""Pytest configuration for the trading-bot test suite."""

import pytest


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    """Restrict anyio-marked async tests to the asyncio backend only.

    The trading engine is built on asyncio; trio is not supported.
    """
    return request.param
