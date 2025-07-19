#!/usr/bin/env python3
"""
Stock Analysis Telegram Bot
功能：
  /start  /help                 基本介紹
  /price  <ticker>              即時價格
  /ta     <ticker> <KD|RSI>     技術指標
  /fibo   <ticker>              斐波那契回撤位
  /fund   <ticker>              簡易基本面 (市值、本益比…)
支援：
  - 台股：2330 -> 2330.TW (yfinance) 或 twstock
  - 美股：AAPL, MSFT, TSLA…
"""

import os
import io
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler
)

# --- 基本設定 -------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
TOKEN = os.environ.get("TG_TOKEN")  # 請在 .env 或雲端環境變數設定

TZ_TAIPEI = timezone(timedelta(hours=8))


# --- 資料抓取工具 ----------------------------------------------------------
def normalize_ticker(raw: str) -> str:
    """將使用者輸入轉成 yfinance 可用的代碼"""
    t = raw.upper()
    if t.isdigit():          # 台股數字代碼
        return f"{t}.TW"
    return t                 # 其餘視為美股 / ETF 代碼


def fetch_yf(ticker: str, period="6mo", interval="1d") -> pd.DataFrame:
    data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError("查無此股票或資料來源暫時無回應")
    return data


# --- 指令實作 --------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 嗨！我是股票分析 Bot。\n"
        "輸入 /help 查看所有可用指令。"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 *指令列表*\n"
        "/price `<代碼>` – 查詢即時股價\n"
        "/ta `<代碼>` `<KD|RSI>` – 畫出技術指標\n"
        "/fibo `<代碼>` – 近 6 個月斐波那契回撤\n"
        "/fund `<代碼>` – 基本面摘要\n"
        "\n範例：\n"
        "`/price 2330`  (台灣台積電)\n"
        "`/price tesla`  (美股特斯拉)\n"
        "`/ta AAPL KD`"
        , parse_mode="Markdown"
    )


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法：/price `<股票代碼>`")
        return
    raw = context.args[0]
    yf_tkr = normalize_ticker(raw)
    try:
        quote = yf.Ticker(yf_tkr).fast_info
        price = quote["last_price"]
        chg = quote["last_price"] - quote["previous_close"]
        pct = chg / quote["previous_close"] * 100
        msg = f"💹 {raw.upper()} 現價 *{price:,.2f}* ({chg:+.2f}, {pct:+.2f}%)"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ 無法取得價格，請確認代碼。")


async def plot_and_send(update: Update, df: pd.DataFrame, title: str):
    """將圖表畫好後傳給 Telegram"""
    buf = io.BytesIO()
    plt.figure()                       # 單圖，避免子圖
    df.plot()
    plt.title(title)
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    await update.message.reply_photo(InputFile(buf, filename="chart.png"))


async def cmd_ta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("用法：/ta `<代碼>` `<KD|RSI>`")
        return
    raw, ind = context.args[0], context.args[1].upper()
    yf_tkr = normalize_ticker(raw)
    try:
        df = fetch_yf(yf_tkr, period="6mo")
        if ind == "RSI":
            delta = df["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - 100 / (1 + rs)
            await plot_and_send(update, rsi.rename("RSI"), f"{raw.upper()} RSI (14)")
        elif ind == "KD":
            low_min = df["Low"].rolling(9).min()
            high_max = df["High"].rolling(9).max()
            rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
            k = rsv.ewm(com=2).mean()
            d = k.ewm(com=2).mean()
            await plot_and_send(update, pd.concat([k.rename("K"), d.rename("D")], axis=1),
                                f"{raw.upper()} KD 指標")
        else:
            await update.message.reply_text("指標僅支援 KD 或 RSI")
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ 計算失敗，請稍後再試或確認代碼。")


async def cmd_fibo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法：/fibo `<代碼>`")
        return
    raw = context.args[0]
    yf_tkr = normalize_ticker(raw)
    try:
        df = fetch_yf(yf_tkr, period="6mo")
        close = df["Close"]
        max_p, min_p = close.max(), close.min()
        levels = [0, .236, .382, .5, .618, .786, 1]
        fibo = {f"{int(l*100)}%": max_p - (max_p - min_p) * l for l in levels}
        txt = "\n".join([f"{k:>4}: {v:,.2f}" for k, v in fibo.items()])
        await update.message.reply_text(f"📐 {raw.upper()} 斐波那契回撤位 (近 6 個月)\n```\n{txt}\n```",
                                        parse_mode="Markdown")
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ 無法計算斐波那契回撤。")


async def cmd_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法：/fund `<代碼>`")
        return
    raw = context.args[0]
    yf_tkr = normalize_ticker(raw)
    try:
        info = yf.Ticker(yf_tkr).fast_info
        fields = {
            "市值": info.get("market_cap"),
            "本益比": info.get("trailing_pe"),
            "股息殖利率": info.get("dividend_yield"),
            "52W 高": info.get("year_high"),
            "52W 低": info.get("year_low"),
        }
        txt = "\n".join([f"{k:<6}: {v:,.2f}" if isinstance(v, (int, float)) else f"{k:<6}: {v}"
                         for k, v in fields.items()])
        await update.message.reply_text(f"📊 {raw.upper()} 基本面\n```\n{txt}\n```",
                                        parse_mode="Markdown")
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("❌ 無法取得基本面資料。")


# --- 主程式 ---------------------------------------------------------------
def main() -> None:
    if not TOKEN:
        raise RuntimeError("請設定環境變數 TG_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start", "hello"], cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("ta", cmd_ta))
    app.add_handler(CommandHandler("fibo", cmd_fibo))
    app.add_handler(CommandHandler("fund", cmd_fund))

    logging.info("Bot started…")
    app.run_polling()


if __name__ == "__main__":
    main()
