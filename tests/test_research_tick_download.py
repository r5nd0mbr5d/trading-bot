import json
from datetime import date

from research.data.tick_download import (
    build_polygon_trades_url,
    convert_polygon_json_to_tick_csv,
    download_polygon_trades_range,
    fetch_polygon_trades_payload,
    polygon_response_to_ticks,
)


def test_build_polygon_trades_url():
    url = build_polygon_trades_url(
        symbol="AAPL",
        trade_date="2026-02-20",
        limit=1000,
        api_key="key123",
    )
    assert "api.polygon.io/v3/trades/AAPL" in url
    assert "limit=1000" in url
    assert "apiKey=key123" in url
    assert "timestamp.gte=" in url and "timestamp.lt=" in url


def test_polygon_response_to_ticks():
    payload = {
        "results": [
            {
                "ticker": "AAPL",
                "sip_timestamp": 1708423200000000000,
                "price": 187.25,
                "size": 10,
            }
        ]
    }

    ticks = polygon_response_to_ticks(payload)
    assert len(ticks) == 1
    assert ticks.iloc[0]["symbol"] == "AAPL"
    assert float(ticks.iloc[0]["price"]) == 187.25


def test_convert_polygon_json_to_tick_csv(tmp_path):
    payload = {
        "results": [
            {
                "ticker": "AAPL",
                "sip_timestamp": 1708423200000000000,
                "price": 187.25,
                "size": 10,
            }
        ]
    }
    source = tmp_path / "polygon.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    out_csv = tmp_path / "ticks.csv"
    result_path = convert_polygon_json_to_tick_csv(source, output_csv=out_csv)

    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    assert "symbol,timestamp,price,size,bid,ask" in content


def test_fetch_polygon_trades_payload_paginates(monkeypatch):
    first_payload = {
        "results": [
            {
                "ticker": "AAPL",
                "sip_timestamp": 1708423200000000000,
                "price": 100.0,
                "size": 1,
            }
        ],
        "next_url": "https://api.polygon.io/v3/trades/AAPL?page=2",
    }
    second_payload = {
        "results": [
            {
                "ticker": "AAPL",
                "sip_timestamp": 1708423201000000000,
                "price": 100.1,
                "size": 2,
            }
        ]
    }

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    calls = {"n": 0}

    def fake_urlopen(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp(first_payload)
        return _Resp(second_payload)

    monkeypatch.setattr("research.data.tick_download.urlopen", fake_urlopen)

    payload = fetch_polygon_trades_payload(
        symbol="AAPL",
        trade_date="2026-02-20",
        api_key="k",
        max_pages=5,
    )

    assert payload["page_count"] == 2
    assert payload["results_count"] == 2
    assert len(payload["results"]) == 2


def test_download_polygon_trades_range_calls_each_day(tmp_path, monkeypatch):
    outputs = []

    def fake_download_polygon_trades_json(**kwargs):
        out = tmp_path / f"polygon_{kwargs['symbol']}_{kwargs['trade_date']}.json"
        out.write_text("{}", encoding="utf-8")
        outputs.append(kwargs["trade_date"])
        return out

    monkeypatch.setattr(
        "research.data.tick_download.download_polygon_trades_json",
        fake_download_polygon_trades_json,
    )

    paths = download_polygon_trades_range(
        symbol="AAPL",
        start_date="2026-02-20",
        end_date="2026-02-22",
        output_dir=tmp_path,
    )

    assert outputs == ["2026-02-20", "2026-02-21", "2026-02-22"]
    assert len(paths) == 3
