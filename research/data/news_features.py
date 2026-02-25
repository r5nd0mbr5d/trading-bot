"""News sentiment feature engineering via Polygon reference news endpoint."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import requests


_POLYGON_NEWS_URL = "https://api.polygon.io/v2/reference/news"
_SENTIMENT_MAP = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _to_utc_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, utc=True)
    return ts.normalize()


def fetch_news(
    symbol: str,
    start_date: str,
    end_date: str,
    api_key: str,
    benzinga_only: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch Polygon news articles for a symbol over a date range.

    Parameters
    ----------
    symbol
        Ticker symbol used in Polygon query.
    start_date
        Inclusive start date string parseable by pandas.
    end_date
        Inclusive end date string parseable by pandas.
    api_key
        Polygon API key used for Bearer authentication.
    benzinga_only
        When ``True``, keep only articles where ``publisher.name`` is Benzinga.

    Returns
    -------
    list[dict]
        Raw article dictionaries from Polygon ``results`` across all pages.

    Raises
    ------
    ValueError
        If symbol/api key/date window is invalid.
    RuntimeError
        If Polygon request fails.
    """
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("symbol is required")
    if not api_key or not api_key.strip():
        raise ValueError("api_key is required")

    start_ts = pd.to_datetime(start_date, utc=True)
    end_ts = pd.to_datetime(end_date, utc=True)
    if start_ts > end_ts:
        raise ValueError("start_date must be <= end_date")

    end_cutoff = end_ts.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    params: Dict[str, Any] | None = {
        "ticker": normalized_symbol,
        "published_utc.gte": start_ts.strftime("%Y-%m-%d"),
        "limit": 50,
    }
    request_url = _POLYGON_NEWS_URL
    articles: List[Dict[str, Any]] = []

    while True:
        try:
            response = requests.get(request_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Polygon news request failed: {exc}") from exc

        payload = response.json() or {}
        page_results = payload.get("results", []) or []

        for article in page_results:
            published = article.get("published_utc")
            if published is None:
                continue
            published_ts = pd.to_datetime(published, utc=True, errors="coerce")
            if pd.isna(published_ts):
                continue
            if published_ts < start_ts or published_ts > end_cutoff:
                continue
            if benzinga_only:
                publisher_name = str(((article.get("publisher") or {}).get("name") or "")).strip()
                if publisher_name.lower() != "benzinga":
                    continue
            articles.append(article)

        next_url = payload.get("next_url")
        if not next_url:
            break
        request_url = str(next_url)
        params = None
        time.sleep(12)

    return articles


def compute_sentiment_features(articles: List[Dict[str, Any]], symbol: str) -> pd.DataFrame:
    """Compute daily news-sentiment feature columns from raw article payloads.

    Parameters
    ----------
    articles
        Raw article dictionaries from Polygon response ``results``.
    symbol
        Ticker symbol used to select matching ``insights[].ticker`` entries.

    Returns
    -------
    pandas.DataFrame
        UTC-aware DatetimeIndex (date-only granularity) with columns:
        ``sentiment_score``, ``article_count``, ``benzinga_count``,
        ``earnings_proximity``.
    """
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("symbol is required")

    columns = [
        "sentiment_score",
        "article_count",
        "benzinga_count",
        "earnings_proximity",
    ]
    if not articles:
        empty_index = pd.DatetimeIndex([], tz="UTC", name="date")
        return pd.DataFrame(columns=columns, index=empty_index)

    rows: List[Dict[str, Any]] = []
    earnings_days: List[pd.Timestamp] = []

    for article in articles:
        published = article.get("published_utc")
        if published is None:
            continue

        published_ts = pd.to_datetime(published, utc=True, errors="coerce")
        if pd.isna(published_ts):
            continue

        day = published_ts.normalize()
        publisher_name = str(((article.get("publisher") or {}).get("name") or "")).strip()

        title = str(article.get("title") or "")
        description = str(article.get("description") or "")
        content_blob = f"{title} {description}".lower()
        has_earnings = "earnings" in content_blob
        if has_earnings:
            earnings_days.append(day)

        sentiment_value = np.nan
        for insight in article.get("insights", []) or []:
            insight_symbol = _normalize_symbol(str(insight.get("ticker") or ""))
            if insight_symbol != normalized_symbol:
                continue
            sentiment_label = str(insight.get("sentiment") or "").strip().lower()
            sentiment_value = _SENTIMENT_MAP.get(sentiment_label, np.nan)
            break

        rows.append(
            {
                "date": day,
                "sentiment_value": sentiment_value,
                "is_benzinga": publisher_name.lower() == "benzinga",
                "has_earnings": has_earnings,
            }
        )

    if not rows:
        empty_index = pd.DatetimeIndex([], tz="UTC", name="date")
        return pd.DataFrame(columns=columns, index=empty_index)

    frame = pd.DataFrame(rows)
    grouped = frame.groupby("date", sort=True)

    features = pd.DataFrame(index=grouped.size().index)
    features.index = pd.DatetimeIndex(features.index, tz="UTC", name="date")
    features["sentiment_score"] = grouped["sentiment_value"].mean()
    features["article_count"] = grouped.size().astype(int)
    features["benzinga_count"] = grouped["is_benzinga"].sum().astype(int)

    if earnings_days:
        earnings_index = pd.DatetimeIndex(sorted(set(earnings_days)), tz="UTC")
        proximity_flags = []
        for day in features.index:
            day_diff = (earnings_index - day).days
            proximity_flags.append(bool((abs(day_diff) <= 3).any()))
        features["earnings_proximity"] = pd.Series(proximity_flags, index=features.index).astype(bool)
    else:
        features["earnings_proximity"] = False

    return features[["sentiment_score", "article_count", "benzinga_count", "earnings_proximity"]]


def build_news_feature_table(
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Build date-aligned news feature table for model feature joins.

    Parameters
    ----------
    symbol
        Ticker symbol to fetch and aggregate.
    start_date
        Inclusive start date string parseable by pandas.
    end_date
        Inclusive end date string parseable by pandas.

    Returns
    -------
    pandas.DataFrame
        UTC-aware daily-index DataFrame with columns:
        ``sentiment_score``, ``article_count``, ``benzinga_count``,
        ``earnings_proximity``.

    Raises
    ------
    RuntimeError
        If ``POLYGON_API_KEY`` is missing.
    """
    api_key = os.getenv("POLYGON_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is required")

    start_day = _to_utc_day(start_date)
    end_day = _to_utc_day(end_date)
    if start_day > end_day:
        raise ValueError("start_date must be <= end_date")

    articles = fetch_news(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
        benzinga_only=False,
    )
    features = compute_sentiment_features(articles, symbol)

    full_index = pd.date_range(start=start_day, end=end_day, freq="D", tz="UTC", name="date")
    features = features.reindex(full_index)

    features["article_count"] = features["article_count"].fillna(0).astype(int)
    features["benzinga_count"] = features["benzinga_count"].fillna(0).astype(int)
    features["earnings_proximity"] = features["earnings_proximity"].fillna(False).astype(bool)

    return features[["sentiment_score", "article_count", "benzinga_count", "earnings_proximity"]]