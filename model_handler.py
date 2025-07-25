"""
model_handler.py
────────────────
Telegram 指令 /model
用法：
  /model 2330          → 預設門檻 prob≥0.70 & RSI<30
  /model 2330 0.6 50   → 自訂門檻
"""
import asyncio, logging, functools
from telegram import Update
from telegram.ext import ContextTypes
from ai_single import analyze_stock

logging.basicConfig(level=logging.INFO)

def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"

async def model_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    chat_id = u.effective_chat.id
    tokens = u.message.text.strip().split()[1:]

    if not tokens:
        await c.bot.send_message(chat_id, "❓ 請輸入股票代碼，例如：/model 2330")
        return

    code = tokens[0]
    prob_thr = float(tokens[1]) if len(tokens) >= 2 else 0.70
    rsi_thr  = float(tokens[2]) if len(tokens) >= 3 else 30

    logging.info(f"/model code={code} prob>={prob_thr} rsi<{rsi_thr}")

    waiting = await c.bot.send_message(chat_id, f"⌛ 正在分析 {code}…")

    loop = asyncio.get_event_loop()
    try:
        # 20 s 逾時保護
        data = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                functools.partial(analyze_stock, code, prob_thr, rsi_thr),
            ),
            timeout=20,
        )
    except asyncio.TimeoutError:
        await waiting.edit_text("⚠️ 連線或計算逾時，請稍後再試")
        return
    except Exception as e:
        # 其餘例外直接回報（仍會被全域 err_handler 捕捉）
        await waiting.edit_text(f"⚠️ 發生錯誤：{e}")
        raise

    if data is None:
        await waiting.edit_text(f"⚠️ 無法取得 {code} 資料或資料不足")
        return

    text = (
        f"*{code}* 近期模型結果\n"
        f"> 機率門檻：≥ {_pct(prob_thr)}\n"
        f"> RSI門檻： < {rsi_thr if rsi_thr is not None else '無'}\n\n"
        f"預測機率： {_pct(data['prob'])}\n"
        f"模型準確： {_pct(data['acc'])}\n"
        f"最新 RSI： {data['rsi']:.1f}\n"
        f"收盤價格： {float(data['close']):,.2f}\n\n"
        f"{data['msg']}"
    )
    await waiting.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)
