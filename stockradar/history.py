from datetime import date, timedelta
import datetime
import requests
import pandas as pd
import yfinance as yf
import twstock

def _twse_month(code: str, y: int, m: int) -> pd.DataFrame:
    ym = f"{y}{m:02d}01"
    url = (
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date="
        f"{ym}&stockNo={code}"
    )
    try:
        j = requests.get(url, timeout=10).json()
    except Exception:
        return pd.DataFrame()
    if j.get("stat") != "OK":
        return pd.DataFrame()
    rows = []
    for r in j["data"]:
        dt = datetime.datetime.strptime(r[0], "%Y/%m/%d")
        rows.append([dt, *[float(x.replace(",", "")) for x in r[3:7]]])
    return pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close"]).set_index("Date")

def _twse_history(code: str, months: int = 6) -> pd.DataFrame:
    today = date.today()
    frames: list[pd.DataFrame] = []
    for i in range(months):
        y, m = divmod(today.year * 12 + today.month - 1 - i, 12)
        m += 1
        frames.append(_twse_month(code, y, m))
    df = pd.concat(frames).sort_index()
    return df.astype(float)

def _yf_history(tk: str, months: int = 6) -> pd.DataFrame:
    tkr = yf.Ticker(tk)
    df = tkr.history(period=f"{months}mo", interval="1d", auto_adjust=True)
    if not df.empty:
        return df.astype(float)
    df = yf.download(tk, period=f"{months}mo", interval="1d", auto_adjust=True, progress=False)
    return df.astype(float)

def get_history(code: str, months: int = 6) -> pd.DataFrame:
    def _is_tw(code: str) -> bool:
        return code.isdigit() or code.upper().endswith(".TW")

    tk = code.upper()
    if not tk.endswith(".TW") and tk.isdigit():
        tk += ".TW"
    df = _yf_history(tk, months)
    if not df.empty:
        return df
    if _is_tw(tk):
        num = tk.split(".")[0]
        df = _twse_history(num, months)
        if not df.empty:
            return df
        stock = twstock.Stock(num)
        start = date.today() - timedelta(days=months * 31)
        raw = stock.fetch_from(start.year, start.month)
        if raw:
            rows = [(x.date, x.open, x.high, x.low, x.close) for x in raw]
            return pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close"]).set_index("Date").astype(float)
    raise ValueError("無法取得歷史資料，稍後再試 🙏")
