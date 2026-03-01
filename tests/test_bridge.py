"""Unit tests for the PAIOS bridge package."""

import pytest

from src.bridge.hooks import (
    make_bar_received_event,
    make_handoff_event,
    make_order_submitted_event,
    make_signal_generated_event,
)
from src.bridge.paios_types import HandoffPacket, SessionConfig, SessionType
from src.bridge.session_classifier import classify_prompt


# ---------------------------------------------------------------------------
# SessionType
# ---------------------------------------------------------------------------


class TestSessionType:
    def test_all_values_are_strings(self):
        for member in SessionType:
            assert isinstance(member.value, str)

    def test_expected_members(self):
        assert set(SessionType) == {
            SessionType.IMPL,
            SessionType.ARCH,
            SessionType.RSRCH,
            SessionType.OPS,
            SessionType.DEBUG,
            SessionType.REVIEW,
        }

    def test_str_enum_equality(self):
        assert SessionType.IMPL == "impl"
        assert SessionType.ARCH == "arch"


# ---------------------------------------------------------------------------
# HandoffPacket
# ---------------------------------------------------------------------------


class TestHandoffPacket:
    def _make_packet(self, **kwargs):
        defaults = dict(
            source_session_type=SessionType.IMPL,
            target_session_type=SessionType.REVIEW,
            summary="Step 63 completed",
            context_files=["src/execution/broker.py", "tests/test_coinbase_broker.py"],
        )
        defaults.update(kwargs)
        return HandoffPacket(**defaults)

    def test_to_dict_serializes_enum_values(self):
        packet = self._make_packet()
        d = packet.to_dict()
        assert d["source_session_type"] == "impl"
        assert d["target_session_type"] == "review"

    def test_to_dict_contains_all_keys(self):
        packet = self._make_packet()
        d = packet.to_dict()
        assert set(d.keys()) == {
            "source_session_type",
            "target_session_type",
            "summary",
            "context_files",
            "parent_job_id",
            "metadata",
        }

    def test_to_dict_context_files(self):
        files = ["src/execution/broker.py", "config/settings.py"]
        packet = self._make_packet(context_files=files)
        assert packet.to_dict()["context_files"] == files

    def test_to_dict_parent_job_id_none_by_default(self):
        packet = self._make_packet()
        assert packet.to_dict()["parent_job_id"] is None

    def test_to_dict_parent_job_id_set(self):
        packet = self._make_packet(parent_job_id="job-abc-123")
        assert packet.to_dict()["parent_job_id"] == "job-abc-123"

    def test_to_dict_metadata_empty_by_default(self):
        packet = self._make_packet()
        assert packet.to_dict()["metadata"] == {}

    def test_to_dict_metadata_populated(self):
        packet = self._make_packet(metadata={"step": 63, "strategy": "CoinbaseBroker"})
        assert packet.to_dict()["metadata"]["step"] == 63

    def test_default_metadata_not_shared(self):
        # Verifies field(default_factory=dict) is used — each instance gets its own dict.
        p1 = self._make_packet()
        p2 = self._make_packet()
        p1.metadata["x"] = 1
        assert "x" not in p2.metadata


# ---------------------------------------------------------------------------
# SessionConfig
# ---------------------------------------------------------------------------


class TestSessionConfig:
    def test_instantiation_with_trading_bot_config(self):
        cfg = SessionConfig(
            type=SessionType.IMPL,
            pre_reads=[
                "IMPLEMENTATION_BACKLOG.md",
                "src/strategies/",
                "src/trading/loop.py",
                ".python-style-guide.md",
            ],
            scope_guard={
                "can_modify_strategy_logic": True,
                "can_change_risk_parameters": False,
                "can_change_broker_config": False,
            },
            description="Pick up and implement backlog steps.",
        )
        assert cfg.type == SessionType.IMPL
        assert "src/strategies/" in cfg.pre_reads
        assert cfg.scope_guard["can_modify_strategy_logic"] is True
        assert cfg.scope_guard["can_change_risk_parameters"] is False

    def test_all_session_types_can_be_configured(self):
        for session_type in SessionType:
            cfg = SessionConfig(
                type=session_type,
                pre_reads=["SESSION_LOG.md"],
                scope_guard={},
                description=f"Config for {session_type.value}",
            )
            assert cfg.type == session_type


# ---------------------------------------------------------------------------
# classify_prompt
# ---------------------------------------------------------------------------


class TestClassifyPrompt:
    @pytest.mark.parametrize(
        "prompt,expected",
        [
            ("deploy the new docker image to staging", SessionType.OPS),
            ("update the CI pipeline config", SessionType.OPS),
            ("setup the environment variables", SessionType.OPS),
            ("there is a bug in the RSI strategy", SessionType.DEBUG),
            ("fix the broken order submission", SessionType.DEBUG),
            ("the backtest crashes on missing data", SessionType.DEBUG),
            ("review the risk manager changes", SessionType.REVIEW),
            ("audit the signal validation logic", SessionType.REVIEW),
            ("validate the Bollinger Band parameters", SessionType.REVIEW),
            ("research the momentum effect on AAPL", SessionType.RSRCH),
            ("backtest the MA crossover on 2023 data", SessionType.RSRCH),
            ("compare the RSI and MACD strategies", SessionType.RSRCH),
            ("analyze the equity curve from last quarter", SessionType.RSRCH),
            ("study the correlation between AAPL and MSFT", SessionType.RSRCH),
            ("investigate the alpha decay over time", SessionType.RSRCH),
            ("refactor the broker factory architecture", SessionType.ARCH),
            ("design a new data pipeline pattern", SessionType.ARCH),
            ("restructure the strategy module", SessionType.ARCH),
            ("implement the CoinbaseBroker integration", SessionType.IMPL),
            ("add the new ATR stops indicator", SessionType.IMPL),
            ("write unit tests for the signal model", SessionType.IMPL),
        ],
    )
    def test_keyword_classification(self, prompt, expected):
        assert classify_prompt(prompt) == expected

    def test_default_falls_back_to_impl(self):
        assert classify_prompt("hello world") == SessionType.IMPL
        assert classify_prompt("") == SessionType.IMPL
        assert classify_prompt("add a new strategy") == SessionType.IMPL

    def test_case_insensitive(self):
        assert classify_prompt("DEPLOY to production") == SessionType.OPS
        assert classify_prompt("BUG in the risk manager") == SessionType.DEBUG

    def test_ops_takes_priority_over_debug(self):
        # "config" is OPS; "error" is DEBUG — OPS wins because it is checked first
        assert classify_prompt("config error") == SessionType.OPS

    def test_debug_takes_priority_over_review(self):
        assert classify_prompt("fix and review the crash") == SessionType.DEBUG


# ---------------------------------------------------------------------------
# hooks — make_bar_received_event
# ---------------------------------------------------------------------------


class TestMakeBarReceivedEvent:
    def test_event_key(self):
        evt = make_bar_received_event("AAPL", {"close": 150.0})
        assert evt["event"] == "bar.received"

    def test_symbol(self):
        evt = make_bar_received_event("NVDA", {"close": 500.0})
        assert evt["symbol"] == "NVDA"

    def test_data_passthrough(self):
        bar = {"open": 100.0, "high": 105.0, "low": 98.0, "close": 103.0, "volume": 1_000_000}
        evt = make_bar_received_event("MSFT", bar)
        assert evt["data"] == bar

    def test_timestamp_present(self):
        evt = make_bar_received_event("AAPL", {})
        assert "timestamp" in evt
        assert evt["timestamp"].endswith("+00:00")


# ---------------------------------------------------------------------------
# hooks — make_signal_generated_event
# ---------------------------------------------------------------------------


class TestMakeSignalGeneratedEvent:
    def test_event_key(self):
        evt = make_signal_generated_event("AAPL", "buy", 0.85)
        assert evt["event"] == "signal.generated"

    def test_fields(self):
        evt = make_signal_generated_event("TSLA", "sell", 0.6)
        assert evt["symbol"] == "TSLA"
        assert evt["signal"] == "sell"
        assert evt["confidence"] == 0.6

    def test_timestamp_present(self):
        evt = make_signal_generated_event("AAPL", "hold", 0.5)
        assert "timestamp" in evt


# ---------------------------------------------------------------------------
# hooks — make_order_submitted_event
# ---------------------------------------------------------------------------


class TestMakeOrderSubmittedEvent:
    def test_event_key(self):
        evt = make_order_submitted_event("ord-001", "AAPL", "buy", 10.0)
        assert evt["event"] == "order.submitted"

    def test_fields(self):
        evt = make_order_submitted_event("ord-999", "GOOG", "sell", 5.5)
        assert evt["order_id"] == "ord-999"
        assert evt["symbol"] == "GOOG"
        assert evt["side"] == "sell"
        assert evt["qty"] == 5.5

    def test_timestamp_present(self):
        evt = make_order_submitted_event("x", "y", "buy", 1.0)
        assert "timestamp" in evt


# ---------------------------------------------------------------------------
# hooks — make_handoff_event
# ---------------------------------------------------------------------------


class TestMakeHandoffEvent:
    def _packet(self):
        return HandoffPacket(
            source_session_type=SessionType.IMPL,
            target_session_type=SessionType.REVIEW,
            summary="Implementation done, needs review",
            context_files=["src/bridge/paios_types.py"],
            parent_job_id="job-42",
            metadata={"step": 64},
        )

    def test_event_key(self):
        evt = make_handoff_event(self._packet())
        assert evt["event"] == "session.handoff"

    def test_packet_serialized(self):
        evt = make_handoff_event(self._packet())
        assert "packet" in evt
        assert evt["packet"]["source_session_type"] == "impl"
        assert evt["packet"]["target_session_type"] == "review"

    def test_packet_metadata(self):
        evt = make_handoff_event(self._packet())
        assert evt["packet"]["metadata"]["step"] == 64

    def test_timestamp_present(self):
        evt = make_handoff_event(self._packet())
        assert "timestamp" in evt
