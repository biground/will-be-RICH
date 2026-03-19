"""
综合类技术指标信号生成
每个函数返回列表 [(entries, exits, name), ...]
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from config import INDICATOR_PARAMS


def sar_signals(df: pd.DataFrame) -> list[tuple]:
    """SAR抛物线 / Parabolic SAR: SAR在价格下方→做多，SAR在价格上方→做空"""
    p = INDICATOR_PARAMS["sar"]
    sar = ta.psar(df["high"], df["low"], df["close"], af0=p["af"], af=p["af"], max_af=p["max_af"])

    # pandas_ta psar 输出: PSARl (long), PSARs (short), PSARaf, PSARr
    long_col = [c for c in sar.columns if c.startswith("PSARl")][0]
    short_col = [c for c in sar.columns if c.startswith("PSARs")][0]
    psar_long = sar[long_col]   # 做多SAR值(价格上方时为NaN)
    psar_short = sar[short_col]  # 做空SAR值(价格下方时为NaN)

    # 做多信号: SAR从做空翻转为做多（psar_long从NaN变为有值）
    entries = psar_long.notna() & psar_long.shift(1).isna()
    # 做空信号: SAR从做多翻转为做空（psar_short从NaN变为有值）
    exits = psar_short.notna() & psar_short.shift(1).isna()
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"SAR({p['af']},{p['max_af']})")]


def ichimoku_signals(df: pd.DataFrame) -> list[tuple]:
    """
    Ichimoku云图:
    - 买入: 价格在云图上方（close > senkou_span_a 和 close > senkou_span_b）
    - 卖出: 价格在云图下方
    """
    p = INDICATOR_PARAMS["ichimoku"]
    ichi = ta.ichimoku(df["high"], df["low"], df["close"],
                       tenkan=p["tenkan"], kijun=p["kijun"], senkou=p["senkou"])
    if isinstance(ichi, tuple):
        ichi_df = ichi[0]
    else:
        ichi_df = ichi

    # 查找 Senkou Span A 和 B 列
    ssa_col = [c for c in ichi_df.columns if "ISA" in c or "SSA" in c or "Senkou" in c.replace(" ", "")][0]
    ssb_col = [c for c in ichi_df.columns if "ISB" in c or "SSB" in c][0]
    span_a = ichi_df[ssa_col]
    span_b = ichi_df[ssb_col]
    cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bot = pd.concat([span_a, span_b], axis=1).min(axis=1)

    # 价格从云图下方穿越到上方买入
    above_cloud = df["close"] > cloud_top
    entries = above_cloud & (~above_cloud.shift(1).fillna(True))

    # 价格从云图上方跌入下方卖出
    below_cloud = df["close"] < cloud_bot
    exits = below_cloud & (~below_cloud.shift(1).fillna(True))

    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Ichimoku({p['tenkan']},{p['kijun']},{p['senkou']})")]


def supertrend_signals(df: pd.DataFrame) -> list[tuple]:
    """SuperTrend: 趋势翻转信号"""
    p = INDICATOR_PARAMS["supertrend"]
    st = ta.supertrend(df["high"], df["low"], df["close"],
                       length=p["period"], multiplier=p["mult"])

    # pandas_ta supertrend 输出: SUPERT_{period}_{mult}, SUPERTd_{period}_{mult}, SUPERTl, SUPERTs
    direction_col = [c for c in st.columns if c.startswith("SUPERTd")][0]
    direction = st[direction_col]  # 1 = 上涨趋势, -1 = 下跌趋势

    entries = (direction == 1) & (direction.shift(1) == -1)
    exits = (direction == -1) & (direction.shift(1) == 1)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"SuperTrend({p['period']},{p['mult']})")]


def get_all_composite_signals(df: pd.DataFrame) -> list[tuple]:
    """汇总所有综合类指标信号"""
    all_signals = []
    all_signals.extend(sar_signals(df))
    all_signals.extend(ichimoku_signals(df))
    all_signals.extend(supertrend_signals(df))
    return all_signals
