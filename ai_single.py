"""
ai_single.py – FINAL stable (pandas 3 fix)
──────────────────────────────────────────
- 使用 NumPy 陣列 + 明確 feature_name
- 關鍵修正：最後一筆收盤/RSI 改用 .iloc[-1]
"""
from __future__ import annotations
import datetime, logging, warnings
import lightgbm as lgb, pandas as pd, yfinance as yf
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
TODAY = datetime.date.today()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    gain, loss = d.clip(lower=0), -d.clip(upper=0)
    return 100 - 100 / (1 + gain.rolling(n).mean() / loss.rolling(n).mean())


def analyze_stock(code: str, prob_thr=0.7, rsi_thr: float | None = 30, years=3):
    start = TODAY - datetime.timedelta(days=365 * years)
    df = yf.download(f"{code}.TW", start=start, progress=False, threads=False, auto_adjust=False)
    if df.empty or len(df) < 200:
        return None

    df["sma5"] = df["Close"].rolling(5).mean()
    df["sma20"] = df["Close"].rolling(20).mean()
    df["rsi14"] = rsi(df["Close"])
    df["target"] = (df["Close"].shift(-5) > df["Close"]).astype(int)
    df = df.dropna()
    if df.empty:
        return None

    feats = ["Close", "Volume", "sma5", "sma20", "rsi14"]
    X, y = df[feats], df["target"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, shuffle=False)

    feat_names = [f"f{i}" for i in range(X.shape[1])]
    model = lgb.LGBMClassifier(objective="binary", n_estimators=120, learning_rate=0.05)
    model.fit(Xtr.values, ytr, feature_name=feat_names)

    acc = accuracy_score(yte, model.predict(Xte.values))
    prob = model.predict_proba(X.iloc[[-1]].values)[0][1]
    rsi_now = df["rsi14"].iloc[-1]        # ← fix
    close_now = df["Close"].iloc[-1]      # ← fix

    passed = (prob >= prob_thr) and (rsi_thr is None or rsi_now < rsi_thr)
    return {
        "code": code,
        "acc": acc,
        "prob": prob,
        "rsi": rsi_now,
        "close": close_now,
        "pass_": passed,
        "msg": "✅ 符合條件" if passed else "❌ 未達門檻",
    }


if __name__ == "__main__":
    import sys, json
    print(json.dumps(analyze_stock(sys.argv[1] if len(sys.argv) > 1 else "2330"), indent=2, ensure_ascii=False))
