from __future__ import annotations

import logging
from typing import Any

from bot.market import get_news, get_overnight_moves, load_holdings
from bot.prompts import SEMI_BRIEF_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def build_daily_brief(nim_client: Any) -> str:
    holdings = load_holdings()
    if not holdings:
        return "尚未設定持股清單，請先編輯 bot/holdings.json。"

    tickers = [h["ticker"] for h in holdings]
    moves = get_overnight_moves(tickers)
    news = get_news(tickers)

    if not moves and not news:
        return "今天抓不到任何行情或新聞資料，請檢查網路、API key 或額度。"

    user_content = _format_market_data(holdings, moves, news)
    messages = [
        {"role": "system", "content": SEMI_BRIEF_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    reply = await nim_client.chat(messages)
    return reply or "今天沒有產生內容，請稍後再試。"


def _format_market_data(
    holdings: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    news: list[dict[str, Any]],
) -> str:
    lines: list[str] = ["# 你的持股"]
    for h in holdings:
        weight = h.get("weight")
        suffix = f"（權重 {weight:.0%}）" if isinstance(weight, (int, float)) else ""
        lines.append(f"- {h['ticker']}{suffix}")

    lines.append("\n# 昨晚漲跌（前一交易日收盤 vs 最近收盤）")
    if moves:
        for m in moves:
            lines.append(f"- {m['ticker']}: {m['pct']:+.2f}%（收 {m['last']}）")
    else:
        lines.append("- （無漲跌資料）")

    lines.append("\n# 相關新聞（近 24 小時）")
    if news:
        for n in news[:20]:
            tk = ",".join(t for t in n.get("tickers", []) if t)
            tag = f"[{tk}] " if tk else ""
            lines.append(
                f"- {tag}{n['title']}｜情緒:{n['overall_sentiment']}｜{n['source']}"
            )
            if n.get("summary"):
                lines.append(f"  摘要:{n['summary']}")
    else:
        lines.append("- （無新聞資料）")

    return "\n".join(lines)
