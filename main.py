#!/usr/bin/env python3
"""stock_radar_bot.py – stable rev 2025‑07‑22
================================================
✅ 無語法錯誤，可直接 `python main.py` 執行。
✅ /price /fund /ta /fibo /help（Inline 按鈕切換台股🇹🇼/美股🇺🇸說明）。
✅ /fibo 產生 6 個月日 K 蠟燭圖 + 斐波那契水平線。
✅ /fund 顯示 7 項基本面（市值、PE、PB、EPS、殖利率、52W 高/低）。

requirements.txt
-----------------
python-telegram-bot>=20.8
yfinance>=0.2.40
pandas>=2.2
matplotlib>=3.9
mplfinance>=0.12
requests>=2.32
twstock>=1.3.3
lxml>=4.9
python-dotenv>=1.0
certifi
"""
from __future__ import annotations

# -------------------- Imports & setup ------------------------------------
import os, io, shutil, tempfile, logging, datetime, textwrap
from datetime import date, timedelta, timezone

import certifi, requests, pandas as pd, yfinance as yf, mplfinance as mpf, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import twstock
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
)

# cert workaround (curl‑77)
_tmp_pem = os.path.join(tempfile.gettempdir(), "cacert.pem")
if not os.path.exists(_tmp_pem):
    shutil.copy(certifi.where(), _tmp_pem)
os.environ.update({"SSL_CERT_FILE": _tmp_pem, "REQUESTS_CA_BUNDLE": _tmp_pem})

load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
TZ_TAIPEI = timezone(timedelta(hours=8))

# -------------------- Helpers -------------------------------------------

def _is_tw(code:str)->bool: return code.isdigit() or code.upper().endswith(".TW")

def _norm(code:str)->str:
    c=code.upper()
    if c.isdigit():
        return f"{c}.TW"
    return c

# TWSE JSON

def _twse_month(code:str,y:int,m:int)->pd.DataFrame:
    ym=f"{y}{m:02d}01"
    url=("https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date="
         f"{ym}&stockNo={code}")
    try:
        j=requests.get(url,timeout=10).json()
    except Exception:
        return pd.DataFrame()
    if j.get("stat")!="OK":
        return pd.DataFrame()
    rows=[]
    for r in j["data"]:
        dt=datetime.datetime.strptime(r[0],"%Y/%m/%d")
        rows.append([dt,*[float(x.replace(",","")) for x in r[3:7]]])
    return pd.DataFrame(rows,columns=["Date","Open","High","Low","Close"]).set_index("Date")

def _twse_history(code:str,months:int=6)->pd.DataFrame:
    today=date.today(); frames=[]
    for i in range(months):
        y,m=divmod(today.year*12+today.month-1-i,12); m+=1
        frames.append(_twse_month(code,y,m))
    df=pd.concat(frames).sort_index()
    return df.astype(float)

# yfinance

def _yf_history(tk:str,months:int=6)->pd.DataFrame:
    tkr=yf.Ticker(tk)
    df=tkr.history(period=f"{months}mo",interval="1d",auto_adjust=True)
    if not df.empty:
        return df.astype(float)
    df=yf.download(tk,period=f"{months}mo",interval="1d",auto_adjust=True,progress=False)
    return df.astype(float)

# unified

def get_history(code:str,months:int=6)->pd.DataFrame:
    tk=_norm(code)
    df=_yf_history(tk,months)
    if not df.empty: return df
    if _is_tw(tk):
        num=tk.split(".")[0]
        df=_twse_history(num,months)
        if not df.empty: return df
        stock=twstock.Stock(num)
        start=date.today()-timedelta(days=months*31)
        raw=stock.fetch_from(start.year,start.month)
        if raw:
            rows=[(x.date,x.open,x.high,x.low,x.close) for x in raw]
            return (pd.DataFrame(rows,columns=["Date","Open","High","Low","Close"])\
                    .set_index("Date").astype(float))
    raise ValueError("無法取得歷史資料，稍後再試 🙏")

# misc utils

def _fi(dic:dict,*ks):
    for k in ks:
        v=dic.get(k)
        if v not in (None,""): return v
    return None

def _fmt(v,d:int=2):
    return f"{v:,.{d}f}" if isinstance(v,(int,float)) else "—"

# -------------------- Chart helpers -------------------------------------

def _candle_buf(df:pd.DataFrame,fibo:dict[int,float]|None=None)->io.BytesIO:
    mc=mpf.make_marketcolors(up='r',down='g',inherit=True)
    s=mpf.make_mpf_style(base_mpf_style='yahoo',marketcolors=mc)
    addp=[]
    if fibo:
        for v in fibo.values():
            addp.append(mpf.make_addplot([v]*len(df),color='b',width=0.8))
    fig,_=mpf.plot(df,type='candle',style=s,addplot=addp,datetime_format='%Y-%m',ylabel='Price',returnfig=True)
    buf=io.BytesIO(); fig.savefig(buf,format='png',bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return buf

# -------------------- Telegram Handlers ---------------------------------
async def price_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/price <代碼>")
    raw=c.args[0]
    try:
        tkr=yf.Ticker(_norm(raw))
        fi=tkr.fast_info or {}
        price=_fi(fi,'lastPrice','last_price'); prev=_fi(fi,'previousClose','previous_close')
        if None in (price,prev):
            hist=tkr.history(period='2d'); price,prev=hist['Close'].iloc[-1],hist['Close'].iloc[-2]
        chg,pct=price-prev,(price-prev)/prev*100
        await u.message.reply_text(f"💹 {raw.upper()} 現價 {price:,.2f} ({chg:+.2f}, {pct:+.2f}%)")
    except Exception as e:
        logging.warning(e); await u.message.reply_text("❌ 無法取得價格，稍後再試。")

async def fund_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/fund <代碼>")
    raw=c.args[0]
    try:
        tkr=yf.Ticker(_norm(raw)); fi,info=tkr.fast_info or {},tkr.info or {}
        g=lambda *k:_fi(fi,*k) or info.get(k[-1])
        rows={
            "市值":g('marketCap','market_cap'),
            "本益比":g('trailingPE','trailing_pe'),
            "P/B":info.get('priceToBook'),
            "EPS":info.get('trailingEps'),
            "殖利率":g('dividendYield','dividend_yield'),
            "52W 高":g('yearHigh','year_high','fiftyTwoWeekHigh'),
            "52W 低":g('yearLow','year_low','fiftyTwoWeekLow'),
        }
        txt="\n".join(f"{k:<6}: {_fmt(v)}" for k,v in rows.items())
        await u.message.reply_text(f"📊 {raw.upper()} 基本面一覽\n```\n{txt}\n```",parse_mode="Markdown")
    except Exception as e:
        logging.error(e); await u.message.reply_text("❌ 無法取得基本面資料。")

async def ta_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if len(c.args)<2:
        return await u.message.reply_text("用法：/ta <代碼> KD|RSI")
    raw,ind=c.args[0],c.args[1].upper()
    try:
        df=get_history(raw,6)
        if ind=="RSI":
            delta=df['Close'].diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
            rs=gain/loss; rsi=100-100/(1+rs)
            fig,ax=plt.subplots(); rsi.plot(ax=ax); ax.set_title(f"{raw.upper()} RSI(14)"); ax.set_ylim(0,100); ax.axhline(70,color='r'); ax.axhline(30,color='g'); buf=io.BytesIO(); fig.savefig(buf,format='png'); plt.close(fig); buf.seek(0)
            await u.message.reply_photo(InputFile(buf,"rsi.png"))
        elif ind=="KD":
            low_min=df['Low'].rolling(9).min(); high_max=df['High'].rolling(9).max()
            rsv=(df['Close']-low_min)/(high_max-low_min)*100; k=rsv.ewm(com=2).mean(); d=k.ewm(com=2).mean()
            fig,ax=plt.subplots(); k.plot(ax=ax,label='K'); d.plot(ax=ax,label='D'); ax.set_title(f"{raw.upper()} KD 指標"); ax.legend(); buf=io.BytesIO(); fig.savefig(buf,format='png'); plt.close(fig); buf.seek(0)
            await u.message.reply_photo(InputFile(buf,"kd.png"))
        else:
            await u.message.reply_text("指標僅支援 KD 或 RSI")
    except Exception as e:
        logging.error(e); await u.message.reply_text("❌ 計算失敗，可能資料源暫時無回應。")

async def fibo_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if not c.args:
        return await u.message.reply_text("用法：/fibo <代碼>")
    raw=c.args[0]
    try:
        df=get_history(raw,6)
        close=df['Close']; hi,lo=close.max(),close.min()
        levels={int(p*100):hi-(hi-lo)*p for p in (0,.236,.382,.5,.618,.786,1)}
        buf=_candle_buf(df,levels)
        txt="\n".join(f"{k:>4}%: {_fmt(v)}" for k,v in levels.items())
        await u.message.reply_photo(InputFile(buf,"fibo.png"),caption=f"🔮 {raw.upper()} 斐波那契回撤\n```\n{txt}\n```",parse_mode="Markdown")
    except Exception as e:
        logging.error(e); await u.message.reply_text("❌ 無法計算斐波那契回撤。")

# /help with buttons

def _help_markup():
    kb=[[InlineKeyboardButton("🇹🇼 台股專區",callback_data="help_tw"),InlineKeyboardButton("🇺🇸 美股專區",callback_data="help_us")]]
    return InlineKeyboardMarkup(kb)

HELP_TW=textwrap.dedent("""
📖 *台股專區*
/price 2330 – 即時報價
/fund  2330 – 基本面
/ta    2330 KD – 技術指標
/fibo  2330 – 回撤圖
""")
HELP_US=textwrap.dedent("""
📖 *美股專區*
/price AAPL
/fund  TSLA
/ta    NVDA RSI
/fibo  MSFT
""")

async def help_cmd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(HELP_TW,parse_mode="Markdown",reply_markup=_help_markup())

async def help_cb(u:Update,c:ContextTypes.DEFAULT_TYPE):
    q=u.callback_query; await q.answer()
    if q.data=="help_us":
        await q.edit_message_text(HELP_US,parse_mode="Markdown",reply_markup=_help_markup())
    elif q.data=="help_tw":
        await q.edit_message_text(HELP_TW,parse_mode="Markdown",reply_markup=_help_markup())

# start alias
async def start_cmd(u:Update,c):
    await u.message.reply_text("嗨！輸入 /help 觀看指令 📜")

# -------------------- main ----------------------------------------------
def main():
    if not TOKEN:
        raise RuntimeError("請設定環境변수 TG_TOKEN")
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start","hello"],start_cmd))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CallbackQueryHandler(help_cb))
    app.add_handler(CommandHandler("price",price_cmd))
    app.add_handler(CommandHandler("fund",fund_cmd))
    app.add_handler(CommandHandler("ta",ta_cmd))
    app.add_handler(CommandHandler("fibo",fibo_cmd))
    logging.info("Bot started…"); app.run_polling(allowed_updates=["message","callback_query"])

if __name__=="__main__":
    main()
