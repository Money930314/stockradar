from __future__ import annotations
import os, io, shutil, tempfile, logging, datetime
from datetime import date, timedelta, timezone

import certifi
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

from stock_info_handler import price_cmd, fund_cmd, ta_cmd, fibo_cmd
from pattern_detector import pattern_cmd, pattern_help_cmd
from news_handler import news_cmd
from top10_handler import top10_cmd


# ---------- cert workaround (curl‑77) -----------------------------------
_tmp_pem = os.path.join(tempfile.gettempdir(), "cacert.pem")
if not os.path.exists(_tmp_pem):
    shutil.copy(certifi.where(), _tmp_pem)
os.environ.update({"SSL_CERT_FILE": _tmp_pem, "REQUESTS_CA_BUNDLE": _tmp_pem})

# ---------- env / logging ------------------------------------------------
load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
TZ_TAIPEI = timezone(timedelta(hours=8))

# -------------------- Telegram Texts ------------------------------------
WELCOME_TEXT = (
    "✨ *嗨嗨！歡迎來到 Stock Radar Bot* 🎯\n\n"
    "我可以協助快速掌握股票資訊：\n"
    "• 💹 `/price 2330` → 即時報價\n"
    "• 📊 `/fund 2330`  → 基本面 7-合-1\n"
    "• 📐 `/ta 2330 KD` → KD / RSI 圖\n"
    "• 🔮 `/fibo 2330`  → 6M 日 K + 斐波那契\n\n"
    "👉 輸入 /help 或直接丟代碼給我試試！🚀"
)
HELP_TW = (
    "🏮 *台股專區* ─ 指令快速鍵\n"
    "👉 `/price 2330`  💹 價格\n"
    "👉 `/fund 2603`   📊 基本面\n"
    "👉 `/ta 2303 KD`  📐 KD 指標\n"
    "👉 `/fibo 0050`   🔮 回撤線\n\n"
    "📌 小提醒：台股輸入純數字即可。"
)
HELP_US = (
    "🗽 *美股專區* ─ 指令快速鍵\n"
    "👉 `/price AAPL`  💹 價格\n"
    "👉 `/fund TSLA`   📊 基本面\n"
    "👉 `/ta MSFT RSI` 📐 RSI 圖\n"
    "👉 `/fibo NVDA`   🔮 回撤線\n\n"
    "📌 小提醒：ETF 也行，例如 SPY、QQQ。"
)
TA_HELP = (
    "📐 *技術分析小抄* ─ 指令範例\n"
    "👉 `/pattern 2330`   🔍 W底 / M頭 / 頭肩頂…\n"
    "👉 `/patternhelp`    📚 型態教學\n\n"
    "範例：\n"
    "• 想掃 NVIDIA 有沒有反轉 → `/pattern NVDA`\n"
    "• 想看指令列表           → `/patternhelp`\n"
)
NEWS_HELP = (
    "📰 *新聞專區* ─ 指令範例\n"
    "👉 `/news industry AI`    🤖 產業新聞\n"
    "👉 `/news policy 升息`    🏛️ 政策新聞\n\n"
    "🔎 支援任意關鍵字，快速掌握市場脈動！"
)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def _help_keyboard(active: str = "tw") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🇹🇼 台股專區 ✅" if active == "tw" else "🇹🇼 台股專區",
                callback_data="help_tw"
            ),
            InlineKeyboardButton(
                "🇺🇸 美股專區 ✅" if active == "us" else "🇺🇸 美股專區",
                callback_data="help_us"
            ),
        ],
        [
            InlineKeyboardButton(
                "📐 技術分析 ✅" if active == "ta" else "📐 技術分析",
                callback_data="help_ta"
            ),
            InlineKeyboardButton(
                "📰 新聞專區 ✅" if active == "news" else "📰 新聞專區",
                callback_data="help_news"
            ),
        ],
    ])


# -------------------- Handlers ------------------------------------------
async def start_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    from TG_notifier import send_text
    await send_text(c, u.effective_chat.id, WELCOME_TEXT, parse_mode="Markdown")

async def help_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    from TG_notifier import send_text
    await send_text(c, u.effective_chat.id, HELP_TW, parse_mode="Markdown", reply_markup=_help_keyboard())

async def help_cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()

    key = q.data  # help_tw / help_us / help_ta / help_news

    if key == "help_us":
        await q.edit_message_text(HELP_US,   parse_mode="Markdown",
                                  reply_markup=_help_keyboard("us"))
    elif key == "help_tw":
        await q.edit_message_text(HELP_TW,   parse_mode="Markdown",
                                  reply_markup=_help_keyboard("tw"))
    elif key == "help_ta":
        await q.edit_message_text(TA_HELP,   parse_mode="Markdown",
                                  reply_markup=_help_keyboard("ta"))
    elif key == "help_news":
        await q.edit_message_text(NEWS_HELP, parse_mode="Markdown",
                                  reply_markup=_help_keyboard("news"))

# -------------------- main ----------------------------------------------
def main():
    if not TOKEN:
        raise RuntimeError("請設定環境變數 TG_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "hello"], start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(help_cb))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("fund", fund_cmd))
    app.add_handler(CommandHandler("ta", ta_cmd))
    app.add_handler(CommandHandler("fibo", fibo_cmd))
    app.add_handler(CommandHandler("pattern", pattern_cmd))
    app.add_handler(CommandHandler("patternhelp", pattern_help_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("top10", top10_cmd))
    logging.info("Bot started…")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
