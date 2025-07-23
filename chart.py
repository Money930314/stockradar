import mplfinance as mpf
import matplotlib.pyplot as plt
import io
import pandas as pd

def _candle_buf(df: pd.DataFrame, fibo: dict[int, float] | None = None) -> io.BytesIO:
    mc = mpf.make_marketcolors(up="r", down="g", inherit=True)
    s = mpf.make_mpf_style(base_mpf_style="yahoo", marketcolors=mc)
    addp = []
    if fibo:
        for v in fibo.values():
            addp.append(mpf.make_addplot([v] * len(df), color="b", width=0.8))
    fig, _ = mpf.plot(
        df,
        type="candle",
        style=s,
        addplot=addp,
        datetime_format="%Y-%m",
        ylabel="Price",
        returnfig=True
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
