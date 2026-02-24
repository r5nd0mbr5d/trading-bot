import asyncio
import json
import sys

from config.settings import Settings
from src.data.feeds import MarketDataFeed


class _FakeWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        if not self._messages:
            await asyncio.sleep(0)
            return json.dumps([])
        return self._messages.pop(0)


def test_websocket_feed_emits_bars(monkeypatch):
    messages = [
        json.dumps(
            [
                {
                    "ev": "status",
                    "message": "connected",
                    "status": "connected",
                },
                {
                    "ev": "AM",
                    "sym": "AAPL",
                    "s": 1700000000000,
                    "o": 100.0,
                    "h": 101.0,
                    "l": 99.0,
                    "c": 100.5,
                    "v": 1200,
                },
            ]
        )
    ]

    def fake_connect(url, ping_interval=20, ping_timeout=20):
        return _FakeWebSocket(messages)

    class _WSModule:
        connect = staticmethod(fake_connect)

    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "websockets", _WSModule)

    settings = Settings()
    settings.data.source = "polygon"
    settings.broker.provider = "ibkr"

    feed = MarketDataFeed(settings)
    bars = []

    asyncio.run(
        feed.stream(
            ["AAPL"],
            lambda bar: bars.append(bar),
            max_cycles=1,
        )
    )

    assert len(bars) == 1
    assert bars[0].symbol == "AAPL"


def test_websocket_feed_retries_on_error(monkeypatch):
    class _FailingWS:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_connect(url, ping_interval=20, ping_timeout=20):
        return _FailingWS()

    class _WSModule:
        connect = staticmethod(fake_connect)

    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "websockets", _WSModule)

    settings = Settings()
    settings.data.source = "polygon"
    settings.broker.provider = "ibkr"

    feed = MarketDataFeed(settings)
    errors = []

    try:
        asyncio.run(
            feed.stream(
                ["AAPL"],
                lambda bar: None,
                error_callback=lambda payload: errors.append(payload),
                max_cycles=1,
            )
        )
    except RuntimeError as exc:
        assert "websocket_failure_limit_reached" in str(exc)

    assert any(p["event"] == "STREAM_WEBSOCKET_ERROR" for p in errors)
