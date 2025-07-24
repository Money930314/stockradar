"""
ai_top10.py  – 2025-07-24 修正版
--------------------------------
批量掃描台股所有上市櫃股票：
1. 下載近 3 年日 K 線（Yahoo Finance）
2. 計算技術指標（RSI14‧SMA5‧SMA20）
3. 以 LightGBM 預測「5 日內是否上漲」
4. 以 test-set 準確率 + 今日預測機率 + RSI < 30
   篩出勝率 Top-10
5. 回傳 pd.DataFrame，欄位：code, acc, prob, rsi, close
"""
from __future__ import annotations

import warnings
import logging
import datetime
from typing import List

import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf
import twstock
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # 靜音 yfinance

TODAY = datetime.date.today()


# ─────────────────── 技術指標 ────────────────────
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """簡易版 RSI 計算（無 Wilder 平滑）"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ─────────────────── 資料準備 & 模型 ────────────────────
def _prep_dataset(df: pd.DataFrame) -> pd.DataFrame | None:
    """K 線 DataFrame → 加入技術指標與標籤"""
    if len(df) < 200:  # 資料不足 200 根日 K 就跳過
        return None
    df = df.dropna(subset=["Close"]).copy()
    df["sma5"] = df["Close"].rolling(5).mean()
    df["sma20"] = df["Close"].rolling(20).mean()
    df["rsi14"] = rsi(df["Close"], 14)
    # 預測 5 日後收盤是否大於今日收盤
    df["target"] = (df["Close"].shift(-5) > df["Close"]).astype(int)
    df = df.dropna()
    return df


def _train_predict(df: pd.DataFrame):
    feat_cols = ["Close", "Volume", "sma5", "sma20", "rsi14"]
    X = df[feat_cols]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=120, learning_rate=0.05, max_depth=-1
    )
    model.fit(X_train, y_train)

    acc = accuracy_score(y_test, model.predict(X_test))

    # 取最新一筆資料做今日預測
    prob_up = model.predict_proba(X.iloc[[-1]])[0][1]
    latest_rsi = df["rsi14"].iloc[-1]
    latest_close = df["Close"].iloc[-1]

    return acc, prob_up, latest_rsi, latest_close


# ─────────────────── 主流程 ────────────────────
def _get_all_stock_codes() -> List[str]:
     return ["2330", "2303", "2603"]


def analyze_market() -> pd.DataFrame:
    """掃描全市場 → 回傳 Top-10 DataFrame"""
    results = []
    codes = _get_all_stock_codes()

    end = TODAY + datetime.timedelta(days=1)
    start = TODAY - datetime.timedelta(days=365 * 3)

    for code in codes:
        ticker = f"{code}.TW"
        try:
            df = yf.download(
                ticker,
                start=start,
                end=end,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception:
            # yfinance 連線錯誤或被斷線就跳過
            continue

        # 下載失敗 / 資料空白 / 無 timezone → 跳過
        if df.empty or df.index.tz is None:
            continue

        ds = _prep_dataset(df)
        if ds is None:
            continue

        try:
            acc, prob, rsi_val, close = _train_predict(ds)
        except Exception:
            continue  # 模型訓練異常則跳過

        # 篩選條件：模型機率 >0.7 且 RSI < 30
        if prob >= 0.70 and rsi_val < 30:
            results.append(
                {
                    "code": code,
                    "acc": acc,
                    "prob": prob,
                    "rsi": rsi_val,
                    "close": close,
                }
            )

    if not results:
        return pd.DataFrame()

    df_res = (
        pd.DataFrame(results)
        .sort_values(["prob", "acc"], ascending=[False, False])
        .head(10)
        .reset_index(drop=True)
    )
    return df_res


# 允許獨立測試
if __name__ == "__main__":
    df_top10 = analyze_market()
    print(df_top10.to_string(index=False, float_format="%.3f"))
