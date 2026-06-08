from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"


def load_holdings() -> list[dict[str, Any]]:
    path = Path(settings.holdings_path)
    if not path.exists():
        logger.warning("holdings file not found: %s", path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("invalid holdings.json")
        return []
    return [h for h in data if h.get("ticker")]


def get_overnight_moves(tickers: list[str]) -> list[dict[str, Any]]:
    """以前一交易日收盤對比最近收盤，計算漲跌幅。"""
    import yfinance as yf  # 延遲載入，避免啟動變慢

    moves: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                logger.warning("not enough price data for %s", ticker)
                continue
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            pct = (last / prev - 1) * 100 if prev else 0.0
            moves.append(
                {
                    "ticker": ticker,
                    "last": round(last, 2),
                    "prev": round(prev, 2),
                    "pct": round(pct, 2),
                }
            )
        except Exception:
            logger.exception("failed to fetch price for %s", ticker)
    return moves


def get_news(
    tickers: list[str], *, hours: int = 24, limit: int = 50
) -> list[dict[str, Any]]:
    """從 Alpha Vantage NEWS_SENTIMENT 抓取近期、與持股相關的新聞。"""
    if not settings.alphavantage_api_key:
        logger.warning("ALPHAVANTAGE_API_KEY not set; skipping news")
        return []

    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ",".join(tickers),
        "sort": "LATEST",
        "limit": str(limit),
        "apikey": settings.alphavantage_api_key,
    }
    try:
        resp = httpx.get(ALPHAVANTAGE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("failed to fetch news")
        return []

    feed = data.get("feed")
    if not isinstance(feed, list):
        # 額度用盡時 Alpha Vantage 會回 {"Information": ...} 或 {"Note": ...}
        logger.warning("unexpected news response: %s", data)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    watched = set(tickers)
    items: list[dict[str, Any]] = []
    for entry in feed:
        published = _parse_av_time(entry.get("time_published", ""))
        if published and published < cutoff:
            continue
        related = [
            ts.get("ticker")
            for ts in entry.get("ticker_sentiment", [])
            if ts.get("ticker") in watched
        ]
        items.append(
            {
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "source": entry.get("source", ""),
                "url": entry.get("url", ""),
                "overall_sentiment": entry.get("overall_sentiment_label", ""),
                "tickers": related,
            }
        )
    return items


def _parse_av_time(raw: str) -> datetime | None:
    # Alpha Vantage 格式：20240115T130000
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
