"""Unit tests for AuditLogger."""

import pytest

from src.audit.logger import AuditLogger


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "audit.db")


@pytest.fixture
def audit(db_path):
    return AuditLogger(db_path=db_path)


class TestAuditLogger:

    # ------------------------------------------------------------------
    # log → flush → query round-trip
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_log_and_query_basic(self, audit):
        await audit.start()
        await audit.log_event("SIGNAL", {"type": "LONG"}, symbol="AAPL")
        await audit.flush()
        rows = audit.query_events()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "SIGNAL"
        assert rows[0]["symbol"] == "AAPL"
        await audit.stop()

    @pytest.mark.anyio
    async def test_payload_decoded_to_dict(self, audit):
        await audit.start()
        await audit.log_event("ORDER_SUBMITTED", {"qty": 10, "side": "buy"})
        await audit.flush()
        rows = audit.query_events()
        assert isinstance(rows[0]["payload_json"], dict)
        assert rows[0]["payload_json"]["qty"] == 10
        await audit.stop()

    @pytest.mark.anyio
    async def test_multiple_events_all_stored(self, audit):
        await audit.start()
        for i in range(5):
            await audit.log_event("TICK", {"i": i})
        await audit.flush()
        rows = audit.query_events(event_type="TICK")
        assert len(rows) == 5
        await audit.stop()

    # ------------------------------------------------------------------
    # query filters
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_filter_by_event_type(self, audit):
        await audit.start()
        await audit.log_event("SIGNAL", {}, symbol="AAPL")
        await audit.log_event("FILL", {}, symbol="MSFT")
        await audit.flush()
        rows = audit.query_events(event_type="SIGNAL")
        assert all(r["event_type"] == "SIGNAL" for r in rows)
        assert len(rows) == 1
        await audit.stop()

    @pytest.mark.anyio
    async def test_filter_by_symbol(self, audit):
        await audit.start()
        await audit.log_event("SIGNAL", {}, symbol="AAPL")
        await audit.log_event("SIGNAL", {}, symbol="MSFT")
        await audit.flush()
        rows = audit.query_events(symbol="AAPL")
        assert all(r["symbol"] == "AAPL" for r in rows)
        assert len(rows) == 1
        await audit.stop()

    @pytest.mark.anyio
    async def test_filter_by_strategy(self, audit):
        await audit.start()
        await audit.log_event("SIGNAL", {}, strategy="bollinger")
        await audit.log_event("SIGNAL", {}, strategy="ma_cross")
        await audit.flush()
        rows = audit.query_events(strategy="bollinger")
        assert len(rows) == 1
        assert rows[0]["strategy"] == "bollinger"
        await audit.stop()

    @pytest.mark.anyio
    async def test_limit_is_respected(self, audit):
        await audit.start()
        for i in range(10):
            await audit.log_event("TICK", {"i": i})
        await audit.flush()
        rows = audit.query_events(limit=3)
        assert len(rows) == 3
        await audit.stop()

    # ------------------------------------------------------------------
    # severity and optional fields
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_severity_stored(self, audit):
        await audit.start()
        await audit.log_event("ERROR", {"msg": "timeout"}, severity="error")
        await audit.flush()
        rows = audit.query_events(event_type="ERROR")
        assert rows[0]["severity"] == "error"
        await audit.stop()

    @pytest.mark.anyio
    async def test_null_symbol_and_strategy(self, audit):
        await audit.start()
        await audit.log_event("STARTUP", {"version": "1.0"})
        await audit.flush()
        rows = audit.query_events()
        assert rows[0]["symbol"] is None
        assert rows[0]["strategy"] is None
        await audit.stop()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_stop_and_restart(self, audit):
        await audit.start()
        await audit.log_event("A", {})
        await audit.stop()
        # Restart and log another event
        await audit.start()
        await audit.log_event("B", {})
        await audit.flush()
        rows = audit.query_events()
        assert len(rows) == 2
        await audit.stop()

    @pytest.mark.anyio
    async def test_start_idempotent(self, audit):
        await audit.start()
        await audit.start()  # second call should be no-op
        await audit.log_event("X", {})
        await audit.flush()
        rows = audit.query_events()
        assert len(rows) == 1
        await audit.stop()

    @pytest.mark.anyio
    async def test_db_persists_between_instances(self, db_path):
        a1 = AuditLogger(db_path=db_path)
        await a1.start()
        await a1.log_event("PERSIST", {"key": "value"})
        await a1.stop()
        # New instance, same DB
        a2 = AuditLogger(db_path=db_path)
        rows = a2.query_events(event_type="PERSIST")
        assert len(rows) == 1
        assert rows[0]["payload_json"]["key"] == "value"
