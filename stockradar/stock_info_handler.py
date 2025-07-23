from telegram import Update, InputFile
from telegram.ext import ContextTypes
import logging, io
import yfinance as yf
from utils import _norm, _fi, _fmt

__all__ = ["price_cmd", "fund_cmd", "ta_cmd", "fibo_cmd"]

import matplotlib.pyplot as plt
import pandas as pd
from history import get_history
from chart import _candle_buf

async def price_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/price <代碼>")
    raw = c.args[0]
    try:
        tkr = yf.Ticker(_norm(raw))
        fi = tkr.fast_info or {}
        price = _fi(fi, 'lastPrice', 'last_price')
        prev = _fi(fi, 'previousClose', 'previous_close')
        if None in (price, prev):
            hist = tkr.history(period='2d')
            price, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
        chg, pct = price - prev, (price - prev) / prev * 100
        await u.message.reply_text(f"\U0001f4b9 {raw.upper()} 現價 {price:,.2f} ({chg:+.2f}, {pct:+.2f}%)")
    except Exception as e:
        logging.warning(e)
        await u.message.reply_text("❌ 無法取得價格，稍後再試。")

async def fund_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/fund <代碼>")
    raw = c.args[0]
    try:
        tkr = yf.Ticker(_norm(raw))
        fi, info = tkr.fast_info or {}, tkr.info or {}
        g = lambda *k: _fi(fi, *k) or info.get(k[-1])
        rows = {
            "市值": g('marketCap', 'market_cap'),
            "本益比": g('trailingPE', 'trailing_pe'),
            "P/B": info.get('priceToBook'),
            "EPS": info.get('trailingEps'),
            "殖利率": g('dividendYield', 'dividend_yield'),
            "52W 高": g('yearHigh', 'year_high', 'fiftyTwoWeekHigh'),
            "52W 低": g('yearLow', 'year_low', 'fiftyTwoWeekLow'),
        }
        txt = "\n".join(f"{k:<6}: {_fmt(v)}" for k, v in rows.items())
        await u.message.reply_text(
            f"""📊 {raw.upper()} 基本面一覽
```
{txt}
```""",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(e)
        await u.message.reply_text("❌ 無法取得基本面資料。")

async def ta_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if len(c.args) < 2:
        return await u.message.reply_text("用法：/ta <代碼> KD|RSI")
    raw, ind = c.args[0], c.args[1].upper()
    try:
        df = get_history(raw, 6)
        if ind == "RSI":
            delta = df['Close'].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - 100 / (1 + rs)
            fig, ax = plt.subplots()
            rsi.plot(ax=ax)
            ax.set_title(f"{raw.upper()} RSI(14)")
            ax.set_ylim(0, 100)
            ax.axhline(70, color='r')
            ax.axhline(30, color='g')
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            plt.close(fig)
            buf.seek(0)
            await u.message.reply_photo(InputFile(buf, "rsi.png"))
        elif ind == "KD":
            low_min = df['Low'].rolling(9).min()
            high_max = df['High'].rolling(9).max()
            rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
            k = rsv.ewm(com=2).mean()
            d = k.ewm(com=2).mean()
            fig, ax = plt.subplots()
            k.plot(ax=ax, label='K')
            d.plot(ax=ax, label='D')
            ax.set_title(f"{raw.upper()} KD 指標")
            ax.legend()
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            plt.close(fig)
            buf.seek(0)
            await u.message.reply_photo(InputFile(buf, "kd.png"))
        else:
            await u.message.reply_text("指標僅支援 KD 或 RSI")
    except Exception as e:
        logging.error(e)
        await u.message.reply_text("❌ 計算失敗，可能資料源暫時無回應。")

async def fibo_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/fibo <代碼>")
    raw = c.args[0]
    try:
        df = get_history(raw, 6)
        close = df['Close']
        hi, lo = close.max(), close.min()
        levels = {int(p * 100): hi - (hi - lo) * p for p in (0, .236, .382, .5, .618, .786, 1)}
        buf = _candle_buf(df, levels)
        txt = "\n".join(f"{k:>4}%: {_fmt(v)}" for k, v in levels.items())
        await u.message.reply_photo(
            InputFile(buf, "fibo.png"),
            caption=f"""🔮 {raw.upper()} 斐波那契回撤
```
{txt}
```""",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(e)
        await u.message.reply_text("❌ 無法計算斐波那契回撤。")
