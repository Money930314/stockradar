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
from model_handler      import model_cmd

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
    "🏮 *台股專區*\n"
    "🗽 *美股專區*\n"
    "📐 *技術分析*\n"
    "📰 *新聞專區*\n"
    "🤖 *AI 多空雷達預測*\n\n"
    "👉 輸入 /help 或直接丟代碼給我試試！🚀"
)

HELP_TW = (
    "🏮 *台股專區* ─ 指令快速鍵\n"
    "👉 `/price 2330`  💹 即時報價\n"
    "👉 `/fund 2603`   📊 基本面 7合1\n\n"
    "📌 小提醒：台股輸入個股編號即可。"
)
HELP_US = (
    "🗽 *美股專區* ─ 指令快速鍵\n"
    "👉 `/price AAPL`  💹 即時報價\n"
    "👉 `/fund TSLA`   📊 基本面 7合1\n\n"
    "📌 小提醒：ETF 也行，例如 SPY、QQQ。"
)
TA_HELP = (
    "📐 *技術分析* ─ 指令範例\n"
    "💡 `/pattern` <個股代碼>\n\n"
    "👉  /pattern 2330   🔍 W底 / M頭...\n"
    "👉  /patternhelp     📚 型態教學\n"
    "👉  /ta 2303 <RSI/KD>  📐 RSI/KD 指標\n"
    "👉  /fibo 0050    🔮 6M 日 K + 斐波那契\n\n"
    "🔎 支援台股美股 輸入 /patternhelp 快速分析市場！"   
)
NEWS_HELP = (
    "📰 *新聞專區* ─ 指令範例\n"
    "💡 `/news industry` <任意關鍵字>\n"
    "💡 `/news policy` <任意關鍵字>\n\n"
    "👉 `/news industry AI`    🤖 產業新聞\n"
    "👉 `/news policy 升息`     🏛️ 政策新聞\n\n"
    "🔎 支援任意關鍵字，快速掌握市場脈動！"
)
AI_HELP = (
    "🤖 *AI 多空雷達教學* ─ 指令用法\n"
    "`/model<股票代碼>[機率門檻][RSI門檻]`\n\n"
    "• 機率門檻(預設 0.70)\n"
    "→ 模型對「5 日內上漲」的信心\n"
    "• RSI門檻(預設 30)\n"  
    "→ RSI14 < 門檻才視為超賣\n\n"
    "📈 解讀預測機率：\n"
    "• ≥ 70%    → 🟢 考慮做多\n"
    "• 30~70% → 🟡 觀望\n"
    "• < 30%   → 🔴 下跌風險大，避險／放空\n\n"
    "*Tips*\n"
    "• 高機率 + 低 RSI → 低檔翻揚機會大 \n"
    "• 低機率 + 高 RSI → 漲多拉回風險高\n\n"
    "範例：\n"
    "`/model 2330` (預設門檻)\n"
    "`/model 2603 0.6 50`"
)

# -------------------- Keyboard Layout -----------------------------------
def _help_keyboard(active: str = "tw") -> InlineKeyboardMarkup:
    """active in {'tw','us','ta','news','ai'}"""
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
        [
            InlineKeyboardButton(
                "🤖 AI 多空雷達 ✅" if active == "ai" else "🤖 AI 多空雷達",
                callback_data="help_ai"
            ),
        ],
    ])

# -------------------- Handlers ------------------------------------------
async def start_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    from TG_notifier import send_text
    await send_text(c, u.effective_chat.id, WELCOME_TEXT, parse_mode="Markdown")

async def help_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    from TG_notifier import send_text
    await send_text(
        c, u.effective_chat.id, HELP_TW,
        parse_mode="Markdown", reply_markup=_help_keyboard()
    )

async def help_cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    key = q.data  # help_tw/us/ta/news/ai
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
    elif key == "help_ai":
        await q.edit_message_text(AI_HELP,   parse_mode="Markdown",
                                  reply_markup=_help_keyboard("ai"))

# -------------------- main ----------------------------------------------
def run_bot():
    if not TOKEN:
        raise RuntimeError("請設定環境變數 TG_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    # 指令 handlers
    app.add_handler(CommandHandler(["start", "hello"], start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("fund", fund_cmd))
    app.add_handler(CommandHandler("ta", ta_cmd))
    app.add_handler(CommandHandler("fibo", fibo_cmd))
    app.add_handler(CommandHandler("pattern", pattern_cmd))
    app.add_handler(CommandHandler("patternhelp", pattern_help_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("top10", top10_cmd))
    app.add_handler(CommandHandler("model", model_cmd))

    # Callback (inline button) handler
    app.add_handler(CallbackQueryHandler(help_cb))

    # 全域錯誤回傳 Telegram
    async def err_handler(update, context):
        import traceback, textwrap
        err = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        snippet = textwrap.shorten(err, width=400, placeholder=" … ")
        if update and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                f"⚠️ 例外：\n```{snippet}```",
                parse_mode="Markdown",
            )
        logging.error(err)
    app.add_error_handler(err_handler)

    logging.info("Bot started…")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    run_bot()
