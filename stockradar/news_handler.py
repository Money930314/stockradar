import feedparser
from urllib.parse import quote_plus
from telegram import Update
from telegram.ext import ContextTypes

__all__ = ["news_cmd"]

# ------------------------------------------------------------
# Google News RSS helper
# ------------------------------------------------------------
GOOGLE_NEWS = "https://news.google.com/rss/search?q="

def _dedup(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set(); uniq = []
    for title, link in items:
        if (title, link) not in seen:
            seen.add((title, link)); uniq.append((title, link))
    return uniq

async def _fetch_google(keyword: str, site: str | None = None, max_items: int = 10):
    """Return list of (title, link) via Google News RSS."""
    q = quote_plus(keyword)
    if site:
        q += f"+site:{site}"
    url = f"{GOOGLE_NEWS}{q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [(e.title, e.link) for e in feed.entries[:max_items]]

# ------------------------------------------------------------
# /news 指令主控
# ------------------------------------------------------------
async def news_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text(
            "用法：\n/news industry <關鍵字>\n/news policy <關鍵字>")

    category = c.args[0].lower()
    keyword  = " ".join(c.args[1:]).strip() or "市場"

    # ------------------ Industry ------------------
    if category == "industry":
        hits: list[tuple[str, str]] = []
        # 全網中文(繁) 先抓
        hits += await _fetch_google(keyword, None, 10)
        # 補 CNN、WSJ 英文
        hits += await _fetch_google(keyword, "cnn.com", 5)
        hits += await _fetch_google(keyword, "wsj.com", 5)
        hits = _dedup(hits)
        if not hits:
            return await u.message.reply_text("❌ 未能取得任何新聞結果")
        msg = "\n\n".join(f"📰 {t}\n{l}" for t, l in hits[:10])
        return await u.message.reply_text(msg)

    # ------------------ Policy ------------------
    if category == "policy":
        base_kw = keyword or "央行 升息"
        hits: list[tuple[str, str]] = []
        # 定向來源：Fed、台灣央行、台灣證交所
        hits += await _fetch_google(base_kw, "federalreserve.gov", 5)
        hits += await _fetch_google(base_kw, "cbc.gov.tw", 5)
        hits += await _fetch_google(base_kw, "twse.com.tw", 5)
        # 若仍空白 → 全網補抓
        if not hits:
            hits += await _fetch_google(base_kw, None, 10)
        hits = _dedup(hits)
        if not hits:
            return await u.message.reply_text("❌ 未能取得任何政策新聞")
        msg = "\n\n".join(f"🏛️ {t}\n{l}" for t, l in hits[:10])
        return await u.message.reply_text(msg)

    # 其他分類錯誤
    return await u.message.reply_text(
        "分類請用 industry 或 policy，例如：/news industry AI")
