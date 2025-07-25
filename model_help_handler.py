"""
model_help_handler.py
─────────────────────
Telegram handler for `/modelhelp`.

Displays an illustrated help text that explains how to use the
`/model` command, the meaning of each parameter, and how to
interpret the prediction results.

Import this file in your main bot script and register the command:

    from model_help_handler import model_help_cmd
    app.add_handler(CommandHandler("modelhelp", model_help_cmd))
"""

from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = r"""
🎯 *AI 多空雷達教學指令* (`/modelhelp`)

目前 `/model` 支援即時 **「5 日內漲跌預測」＋「風險燈號」**  

---

### 🔧 支援功能  
• ✅ 預測機率 → 看多／看空信心  
• ✅ RSI 過濾   → 配合超買／超賣區  
• ✅ 雙向策略 → 高機率做多、低機率避險／放空  
• ✅ 自訂門檻 → 機率門檻 & RSI 門檻皆可調  
• ✅ 一次查多檔 → 用空格接多個代碼  

---

### 📜 指令格式  
/model 2330
/model 2603 0.6 50
/model 2317 0.55 none
/model 2330 2303 2603

---

### 📈 燈號說明  
| 預測機率 | 解讀           | 行動建議                   |
|----------|----------------|----------------------------|
| ≥ 70 %   | 多頭信心強      | 🟢　考慮做多／加碼           |
| 30–70 %  | 市場觀望        | 🟡　靜觀其變               |
| < 30 %   | 空頭能量強      | 🔴　*短線下跌風險大* → 避險／放空 |

> *Tips*  
> • 高機率 + 低 RSI → 低檔翻揚機會大  
> • 低機率 + 高 RSI → 漲多拉回風險高  

立即輸入 `/model <代碼>` 試用吧！🚀
""".strip()


async def model_help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the /model help text."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=HELP_TEXT,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
