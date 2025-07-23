import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
import io
from history import get_history
from utils import _norm, _fmt
from telegram import Update, InputFile
from telegram.ext import ContextTypes

__all__ = ["pattern_cmd"]


def detect_double_bottom(df: pd.DataFrame) -> dict:
    lows = df['Low']
    troughs = lows[(lows.shift(1) > lows) & (lows.shift(-1) > lows)]
    if len(troughs) >= 2:
        t1, t2 = troughs.index[-2], troughs.index[-1]
        v1, v2 = troughs.iloc[-2], troughs.iloc[-1]
        if abs(v1 - v2) / v1 < 0.03:
            neckline = df.loc[t1:t2, 'High'].max()
            return {"type": "W 底（雙重底）", "points": (t1, t2), "neckline": neckline}
    return {}

def detect_double_top(df: pd.DataFrame) -> dict:
    highs = df['High']
    peaks = highs[(highs.shift(1) < highs) & (highs.shift(-1) < highs)]
    if len(peaks) >= 2:
        p1, p2 = peaks.index[-2], peaks.index[-1]
        v1, v2 = peaks.iloc[-2], peaks.iloc[-1]
        if abs(v1 - v2) / v1 < 0.03:
            neckline = df.loc[p1:p2, 'Low'].min()
            return {"type": "M 頭（雙重頂）", "points": (p1, p2), "neckline": neckline}
    return {}

def detect_head_shoulders(df: pd.DataFrame) -> dict:
    highs = df['High']
    if len(highs) < 20:
        return {}
    l, h, r = highs[-15:-10].max(), highs[-10:-5].max(), highs[-5:].max()
    if h > l and h > r:
        neckline = min(df['Low'][-10], df['Low'][-5])
        return {"type": "頭肩頂（Head and Shoulders）", "points": (h, l, r), "neckline": neckline}
    return {}

def detect_inverse_head_shoulders(df: pd.DataFrame) -> dict:
    lows = df['Low']
    if len(lows) < 20:
        return {}
    l, h, r = lows[-15:-10].min(), lows[-10:-5].min(), lows[-5:].min()
    if h < l and h < r:
        neckline = max(df['High'][-10], df['High'][-5])
        return {"type": "頭肩底（Inverse H&S）", "points": (h, l, r), "neckline": neckline}
    return {}

def detect_triangle(df: pd.DataFrame) -> dict:
    recent = df[-20:]
    high_trend = recent['High'].rolling(5).max()
    low_trend = recent['Low'].rolling(5).min()
    if (high_trend.max() - high_trend.min()) < (df['High'].max() - df['Low'].min()) * 0.3:
        return {"type": "三角收斂（Triangle）", "points": (), "neckline": df['Close'].iloc[-1]}
    return {}

def detect_flag(df: pd.DataFrame) -> dict:
    recent = df[-20:]
    up = recent['Close'].iloc[0] < recent['Close'].iloc[-1]
    body = recent['High'].max() - recent['Low'].min()
    if body < df['High'].max() * 0.1:
        return {"type": "旗型整理（Flag）", "points": (), "neckline": df['Close'].iloc[-1]}
    return {}

def detect_box(df: pd.DataFrame) -> dict:
    recent = df[-20:]
    box_range = recent['High'].max() - recent['Low'].min()
    if box_range < df['High'].max() * 0.15:
        return {"type": "箱型整理（Rectangle）", "points": (), "neckline": df['Close'].iloc[-1]}
    return {}

def plot_pattern(df: pd.DataFrame, pattern: dict, is_top=False) -> io.BytesIO:
    ap = []
    if pattern:
        neck = pattern['neckline']
        ap.append(mpf.make_addplot([neck] * len(df), color='b'))
    mc = mpf.make_marketcolors(up='r', down='g')
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc)
    fig, _ = mpf.plot(df, type='candle', style=s, addplot=ap, returnfig=True)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

async def pattern_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/pattern <代碼>")
    raw = c.args[0]
    try:
        df = get_history(raw, 6)
        patterns = [
            detect_double_bottom(df),
            detect_double_top(df),
            detect_head_shoulders(df),
            detect_inverse_head_shoulders(df),
            detect_triangle(df),
            detect_flag(df),
            detect_box(df),
        ]
        pattern = next((p for p in patterns if p), None)

        if pattern:
            chart = plot_pattern(df, pattern)
            msg = f"""📈 發現 {pattern['type']} 型態\n
📌 `型態解釋`：
{pattern['type']} 是技術分析中常見的重要趨勢結構，常預示市場方向轉變或整理階段。

📊 `策略建議`：
- 突破／跌破頸線並放量通常確認趨勢。
- 可根據頸線與高低點距離，推估目標價。

📘 若搭配 RSI/MACD/均線同時轉強，可信度更高。"""
            return await u.message.reply_photo(InputFile(chart, "pattern.png"), caption=msg, parse_mode="Markdown")

        return await u.message.reply_text("未偵測到型態 🙏\n支援：W底、M頭、頭肩頂、頭肩底、三角收斂、旗型、箱型整理")



    except Exception as e:
        import logging
        logging.error(e)
        await u.message.reply_text("❌ 偵測失敗，資料來源可能中斷。")

...

async def pattern_help_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 *K 線型態教學指令（/patternhelp）*\n\n"
        "目前支援以下型態辨識：\n"
        "• ✅ W 底（雙重底）\n"
        "• ✅ M 頭（雙重頂）\n"
        "• ✅ 頭肩頂（Head & Shoulders Top）\n"
        "• ✅ 頭肩底（Inverse H&S）\n"
        "• ✅ 三角收斂（Symmetrical Triangle）\n"
        "• ✅ 旗型整理（Flag / Pennant）\n"
        "• ✅ 箱型整理（Rectangle）\n\n"
        "📈 使用方式： `/pattern <股票代碼>`\n"
        "範例： `/pattern 2330`\n\n"
        "分析結果將附圖並回傳趨勢解讀與操作建議 🧠"
    )
    await u.message.reply_text(text, parse_mode="Markdown")

