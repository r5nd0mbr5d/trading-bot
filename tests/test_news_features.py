"""Unit tests for Polygon news sentiment feature integration."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from research.data.news_features import (
    build_news_feature_table,
    compute_sentiment_features,
    fetch_news,
)


def _article(
    *,
    published_utc: str,
    sentiment: str,
    ticker: str = "AAPL",
    publisher: str = "Reuters",
    title: str = "General market update",
    description: str = "No earnings mention",
) -> Dict[str, Any]:
    return {
        "published_utc": published_utc,
        "publisher": {"name": publisher},
        "title": title,
        "description": description,
        "insights": [{"ticker": ticker, "sentiment": sentiment}],
    }


def test_sentiment_score_all_positive():
    articles = [
        _article(published_utc="2026-01-02T10:00:00Z", sentiment="positive"),
        _article(published_utc="2026-01-02T12:00:00Z", sentiment="positive"),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert features.loc[pd.Timestamp("2026-01-02", tz="UTC"), "sentiment_score"] == 1.0


def test_sentiment_score_mixed():
    articles = [
        _article(published_utc="2026-01-03T10:00:00Z", sentiment="positive"),
        _article(published_utc="2026-01-03T12:00:00Z", sentiment="neutral"),
        _article(published_utc="2026-01-03T14:00:00Z", sentiment="negative"),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert features.loc[pd.Timestamp("2026-01-03", tz="UTC"), "sentiment_score"] == 0.0


def test_sentiment_score_empty_returns_nan(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test-key")

    def fake_fetch(*_args, **_kwargs):
        return []

    monkeypatch.setattr("research.data.news_features.fetch_news", fake_fetch)

    features = build_news_feature_table("AAPL", "2026-01-01", "2026-01-03")

    assert np.isnan(features.loc[pd.Timestamp("2026-01-01", tz="UTC"), "sentiment_score"])
    assert np.isnan(features.loc[pd.Timestamp("2026-01-02", tz="UTC"), "sentiment_score"])
    assert np.isnan(features.loc[pd.Timestamp("2026-01-03", tz="UTC"), "sentiment_score"])


def test_article_count_correct():
    articles = [
        _article(published_utc="2026-01-04T09:00:00Z", sentiment="positive"),
        _article(published_utc="2026-01-04T10:00:00Z", sentiment="negative"),
        _article(published_utc="2026-01-04T11:00:00Z", sentiment="neutral"),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert features.loc[pd.Timestamp("2026-01-04", tz="UTC"), "article_count"] == 3


def test_benzinga_only_filter(monkeypatch):
    class _Response:
        def __init__(self, payload: Dict[str, Any]):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Dict[str, Any]:
            return self._payload

    payload = {
        "results": [
            _article(
                published_utc="2026-01-05T09:00:00Z",
                sentiment="positive",
                publisher="Benzinga",
            ),
            _article(
                published_utc="2026-01-05T10:00:00Z",
                sentiment="negative",
                publisher="Reuters",
            ),
        ]
    }

    monkeypatch.setattr(
        "research.data.news_features.requests.get",
        lambda *args, **kwargs: _Response(payload),
    )

    articles = fetch_news(
        symbol="AAPL",
        start_date="2026-01-05",
        end_date="2026-01-05",
        api_key="dummy",
        benzinga_only=True,
    )

    assert len(articles) == 1
    assert articles[0]["publisher"]["name"] == "Benzinga"


def test_earnings_proximity_flag():
    articles = [
        _article(
            published_utc="2026-01-10T09:00:00Z",
            sentiment="neutral",
            title="Company posts earnings preview",
            description="Earnings call expected next week",
        ),
        _article(
            published_utc="2026-01-12T11:00:00Z",
            sentiment="positive",
            title="Product demand rises",
            description="Operational update",
        ),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert bool(features.loc[pd.Timestamp("2026-01-10", tz="UTC"), "earnings_proximity"]) is True
    assert bool(features.loc[pd.Timestamp("2026-01-12", tz="UTC"), "earnings_proximity"]) is True


def test_date_alignment_utc_aware():
    articles = [
        _article(published_utc="2026-01-06T23:59:00+00:00", sentiment="positive"),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert isinstance(features.index, pd.DatetimeIndex)
    assert str(features.index.tz) == "UTC"
    assert features.index[0].hour == 0
    assert features.index[0].minute == 0


def test_multi_day_aggregation():
    articles = [
        _article(published_utc="2026-01-07T09:00:00Z", sentiment="positive"),
        _article(published_utc="2026-01-07T10:00:00Z", sentiment="negative"),
        _article(published_utc="2026-01-08T09:00:00Z", sentiment="neutral"),
    ]

    features = compute_sentiment_features(articles, "AAPL")

    assert list(features.index) == [
        pd.Timestamp("2026-01-07", tz="UTC"),
        pd.Timestamp("2026-01-08", tz="UTC"),
    ]
    assert features.loc[pd.Timestamp("2026-01-07", tz="UTC"), "article_count"] == 2
    assert features.loc[pd.Timestamp("2026-01-08", tz="UTC"), "article_count"] == 1
