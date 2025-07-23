def _norm(code: str) -> str:
    """將股票代碼標準化（台股加上 .TW）"""
    c = code.upper()
    return f"{c}.TW" if c.isdigit() else c

def _fi(dic: dict, *ks):
    """從 dict 中依序取第一個不為空的欄位"""
    for k in ks:
        v = dic.get(k)
        if v not in (None, ""):
            return v
    return None

def _fmt(v, d: int = 2):
    """格式化數字加上逗號，若非數字則回傳 em dash"""
    return f"{v:,.{d}f}" if isinstance(v, (int, float)) else "—"
