"""
波动率类技术指标信号生成
每个函数返回列表 [(entries, exits, name), ...]
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from config import INDICATOR_PARAMS


def atr_breakout_signals(df: pd.DataFrame) -> list[tuple]:
    """ATR 突破: 价格突破前日收盘±ATR倍数"""
    p = INDICATOR_PARAMS["atr"]
    atr = ta.atr(df["high"], df["low"], df["close"], length=p["period"])
    prev_close = df["close"].shift(1)
    upper = prev_close + p["mult"] * atr
    lower = prev_close - p["mult"] * atr

    entries = (df["close"] > upper)
    exits = (df["close"] < lower)
    # 去重复
    entries = entries & (~entries.shift(1).fillna(False))
    exits = exits & (~exits.shift(1).fillna(False))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"ATR_Breakout({p['period']},{p['mult']})")]


def hist_vol_signals(df: pd.DataFrame) -> list[tuple]:
    """
    历史波动率: 波动率从收缩转为扩张时买入（类似布林带收窄后突破）。
    使用波动率与其均值的关系判断。
    """
    p = INDICATOR_PARAMS["hist_vol"]
    period = p["period"]
    # 计算历史波动率
    log_ret = np.log(df["close"] / df["close"].shift(1))
    hist_vol = log_ret.rolling(window=period).std() * np.sqrt(252)
    vol_ma = hist_vol.rolling(window=period).mean()

    # 波动率从低于均值收缩状态穿越到高于均值 → 突破信号
    # 配合价格方向确定买卖
    vol_expanding = (hist_vol > vol_ma) & (hist_vol.shift(1) <= vol_ma.shift(1))
    price_up = df["close"] > df["close"].shift(period)
    price_dn = df["close"] < df["close"].shift(period)

    entries = vol_expanding & price_up
    exits = vol_expanding & price_dn
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"HistVol({period})")]


def keltner_vol_signals(df: pd.DataFrame) -> list[tuple]:
    """Keltner 通道波动率版: 布林带在KC通道内部收缩后的突破信号（Squeeze）"""
    p_bb = INDICATOR_PARAMS["bollinger"]
    p_kc = INDICATOR_PARAMS["keltner"]

    bb = ta.bbands(df["close"], length=p_bb["period"], std=p_bb["std"])
    kc = ta.kc(df["high"], df["low"], df["close"],
               length=p_kc["period"], scalar=p_kc["mult"])

    bbl_col = [c for c in bb.columns if c.startswith("BBL")][0]
    bbu_col = [c for c in bb.columns if c.startswith("BBU")][0]
    kcl_col = [c for c in kc.columns if c.startswith("KCL")][0]
    kcu_col = [c for c in kc.columns if c.startswith("KCU")][0]

    bb_lower = bb[bbl_col]
    bb_upper = bb[bbu_col]
    kc_lower = kc[kcl_col]
    kc_upper = kc[kcu_col]

    # Squeeze: BB在KC内部 → 收缩状态
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    squeeze_off = ~squeeze_on

    # Squeeze释放信号
    release = squeeze_off & squeeze_on.shift(1).fillna(False)
    price_momentum = df["close"] - df["close"].shift(p_bb["period"])

    entries = release & (price_momentum > 0)
    exits = release & (price_momentum < 0)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, "KC_Squeeze")]


def doji_signals(df: pd.DataFrame) -> list[tuple]:
    """十字星形态: 实体很小的K线出现在趋势末端，配合前期趋势判断反转"""
    body = abs(df["close"] - df["open"])
    hl_range = df["high"] - df["low"]
    # 十字星定义: 实体 < 总振幅的10%
    is_doji = (body < hl_range * 0.1) & (hl_range > 0)

    # 前5日趋势
    prev_trend = df["close"].rolling(5).apply(
        lambda x: 1 if x.iloc[-1] > x.iloc[0] else (-1 if x.iloc[-1] < x.iloc[0] else 0),
        raw=False
    )

    # 下跌趋势中出现十字星 → 潜在反转买入
    entries = is_doji & (prev_trend == -1)
    # 上涨趋势中出现十字星 → 潜在反转卖出
    exits = is_doji & (prev_trend == 1)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, "DOJI")]


def get_all_volatility_signals(df: pd.DataFrame) -> list[tuple]:
    """汇总所有波动率类指标信号"""
    all_signals = []
    all_signals.extend(atr_breakout_signals(df))
    all_signals.extend(hist_vol_signals(df))
    all_signals.extend(keltner_vol_signals(df))
    all_signals.extend(doji_signals(df))
    return all_signals
