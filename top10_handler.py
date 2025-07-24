"""
top10_handler.py
----------------
Telegram 指令 /top10
執行 AI 模型 → 回傳勝率前十名股票的表格
"""
import asyncio, pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from TG_notifier import send_text
from ai_top10 import analyze_market

_TABLE_HDR = ("代碼", "準確率", "機率", "RSI14", "收盤")

def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"

def _df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "❌ 今日無符合條件的標的"
    lines = ["*今日 AI 預測勝率前 10 名*"]
    hdr = " | ".join(_TABLE_HDR)
    sep = " | ".join(["---"] * len(_TABLE_HDR))
    lines += [hdr, sep]
    for _, r in df.iterrows():
        lines.append(
            f"{r.code} | {_fmt_pct(r.acc)} | {_fmt_pct(r.prob)} | {r.rsi:.1f} | {r.close:,.2f}")
    return "\n".join(lines)

async def top10_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    chat_id = u.effective_chat.id
    waiting = await c.bot.send_message(chat_id, "⏳ 正在分析全市場，請稍候…")
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, analyze_market)
    text = _df_to_markdown(df)
    await waiting.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)
