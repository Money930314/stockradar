import feedparser, html
from urllib.parse import quote_plus, urlparse
from telegram import Update
from telegram.ext import ContextTypes

__all__ = ["news_cmd"]

GOOGLE_NEWS = "https://news.google.com/rss/search?q="

# ----------------- helpers -----------------

def _dedup(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set(); uniq = []
    for title, link in items:
        if (title, link) not in seen:
            seen.add((title, link)); uniq.append((title, link))
    return uniq


def _fetch_google(keyword: str, site: str | None = None, max_items: int = 10):
    q = quote_plus(keyword)
    if site:
        q += f"+site:{site}"
    url = f"{GOOGLE_NEWS}{q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [(e.title, e.link) for e in feed.entries[:max_items]]


def _domain(link: str) -> str:
    netloc = urlparse(link).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(":" )[0]  # 去掉可能的 :443


def _format_links(hits: list[tuple[str, str]], icon: str) -> str:
    """產生『emoji + 可點標題 (來源)』格式，每條以空行分隔"""
    lines = []
    for idx, (title, link) in enumerate(hits, 1):
        source = _domain(link)
        safe_title = html.escape(title)
        safe_link  = html.escape(link, quote=True)
        lines.append(f"{idx}. {icon} <a href=\"{safe_link}\">{safe_title}</a> ({source})")
    return "\n\n".join(lines)

# ----------------- /news 主指令 -----------------

async def news_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text(
            "用法：\n/news industry <關鍵字>\n/news policy <關鍵字>")

    cat = c.args[0].lower()
    kw  = " ".join(c.args[1:]).strip() or "市場"

    # -------- industry --------
    if cat == "industry":
        hits = _dedup(
            _fetch_google(kw, None, 10) +
            _fetch_google(kw, "cnn.com", 5) +
            _fetch_google(kw, "wsj.com", 5)
        )
        if not hits:
            return await u.message.reply_text("❌ 未能取得任何新聞結果")
        msg = _format_links(hits[:10], "📰")
        return await u.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)

    # -------- policy --------
    if cat == "policy":
        base_kw = kw or "央行 升息"
        hits = _dedup(
            _fetch_google(base_kw, "federalreserve.gov", 5) +
            _fetch_google(base_kw, "cbc.gov.tw", 5) +
            _fetch_google(base_kw, "twse.com.tw", 5) or
            _fetch_google(base_kw, None, 10)
        )
        if not hits:
            return await u.message.reply_text("❌ 未能取得任何政策新聞")
        msg = _format_links(hits[:10], "🏛️")
        return await u.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)

    return await u.message.reply_text("分類請用 industry 或 policy，例如：/news industry AI")
