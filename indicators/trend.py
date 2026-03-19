"""
趋势类技术指标信号生成
每个函数返回列表 [(entries, exits, name), ...]
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from config import INDICATOR_PARAMS


def ma_crossover_signals(df: pd.DataFrame) -> list[tuple]:
    """移动均线金叉/死叉策略 — 快线上穿慢线买入，下穿卖出"""
    results = []
    close = df["close"]
    for fast, slow in INDICATOR_PARAMS["ma_pairs"]:
        ma_fast = ta.sma(close, length=fast)
        ma_slow = ta.sma(close, length=slow)
        entries = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
        exits = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
        entries = entries.fillna(False)
        exits = exits.fillna(False)
        results.append((entries, exits, f"MA({fast},{slow})"))
    return results


def ema_crossover_signals(df: pd.DataFrame) -> list[tuple]:
    """指数移动均线金叉/死叉策略"""
    results = []
    close = df["close"]
    for fast, slow in INDICATOR_PARAMS["ema_pairs"]:
        ema_fast = ta.ema(close, length=fast)
        ema_slow = ta.ema(close, length=slow)
        entries = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        exits = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))
        entries = entries.fillna(False)
        exits = exits.fillna(False)
        results.append((entries, exits, f"EMA({fast},{slow})"))
    return results


def macd_signals(df: pd.DataFrame) -> list[tuple]:
    """MACD柱由负转正买入，由正转负卖出"""
    p = INDICATOR_PARAMS["macd"]
    macd_df = ta.macd(df["close"], fast=p["fast"], slow=p["slow"], signal=p["signal"])
    hist_col = [c for c in macd_df.columns if "h" in c.lower() or "hist" in c.lower()][0]
    hist = macd_df[hist_col]
    entries = (hist > 0) & (hist.shift(1) <= 0)
    exits = (hist < 0) & (hist.shift(1) >= 0)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"MACD({p['fast']},{p['slow']},{p['signal']})")]


def dmi_adx_signals(df: pd.DataFrame) -> list[tuple]:
    """DMI/ADX: DI+上穿DI-且ADX>阈值买入，DI+下穿DI-卖出"""
    p = INDICATOR_PARAMS["dmi"]
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=p["period"])
    # pandas_ta adx outputs: ADX_{period}, DMP_{period}, DMN_{period}
    adx_col = f"ADX_{p['period']}"
    dmp_col = f"DMP_{p['period']}"
    dmn_col = f"DMN_{p['period']}"
    adx_val = adx_df[adx_col]
    di_plus = adx_df[dmp_col]
    di_minus = adx_df[dmn_col]

    cross_up = (di_plus > di_minus) & (di_plus.shift(1) <= di_minus.shift(1))
    cross_down = (di_plus < di_minus) & (di_plus.shift(1) >= di_minus.shift(1))
    entries = cross_up & (adx_val > p["adx_threshold"])
    exits = cross_down
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"DMI/ADX({p['period']})")]


def aroon_signals(df: pd.DataFrame) -> list[tuple]:
    """阿龙通道: AroonUp>上阈值且AroonDown<下阈值买入，反之卖出"""
    p = INDICATOR_PARAMS["aroon"]
    aroon_df = ta.aroon(df["high"], df["low"], length=p["period"])
    up_col = f"AROONU_{p['period']}"
    dn_col = f"AROOND_{p['period']}"
    aroon_up = aroon_df[up_col]
    aroon_dn = aroon_df[dn_col]

    entries = (aroon_up > p["upper_thresh"]) & (aroon_dn < p["lower_thresh"])
    exits = (aroon_dn > p["upper_thresh"]) & (aroon_up < p["lower_thresh"])
    # 只取首次满足条件的信号（去除持续满足期间的重复信号）
    entries = entries & (~entries.shift(1).fillna(False))
    exits = exits & (~exits.shift(1).fillna(False))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Aroon({p['period']})")]


def donchian_signals(df: pd.DataFrame) -> list[tuple]:
    """唐奇安通道: 价格突破上轨买入，跌破下轨卖出"""
    p = INDICATOR_PARAMS["donchian"]
    period = p["period"]
    upper = df["high"].rolling(window=period).max()
    lower = df["low"].rolling(window=period).min()

    entries = (df["close"] > upper.shift(1))
    exits = (df["close"] < lower.shift(1))
    # 去重复
    entries = entries & (~entries.shift(1).fillna(False))
    exits = exits & (~exits.shift(1).fillna(False))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Donchian({period})")]


def bollinger_signals(df: pd.DataFrame) -> list[tuple]:
    """布林带: 价格触下轨买入，触上轨卖出"""
    p = INDICATOR_PARAMS["bollinger"]
    bb = ta.bbands(df["close"], length=p["period"], std=p["std"])
    # pandas_ta bbands: BBL, BBM, BBU, BBB, BBP
    bbl_col = f"BBL_{p['period']}_{p['std']}"
    bbu_col = f"BBU_{p['period']}_{p['std']}"
    lower = bb[bbl_col]
    upper = bb[bbu_col]

    entries = (df["close"] <= lower) & (df["close"].shift(1) > lower.shift(1))
    exits = (df["close"] >= upper) & (df["close"].shift(1) < upper.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Bollinger({p['period']},{p['std']})")]


def keltner_signals(df: pd.DataFrame) -> list[tuple]:
    """KC通道: 价格突破上轨买入，跌破下轨卖出"""
    p = INDICATOR_PARAMS["keltner"]
    kc = ta.kc(df["high"], df["low"], df["close"], length=p["period"], scalar=p["mult"])
    # pandas_ta kc: KCLe, KCBe, KCUe
    kcl_col = [c for c in kc.columns if c.startswith("KCL")][0]
    kcu_col = [c for c in kc.columns if c.startswith("KCU")][0]
    lower = kc[kcl_col]
    upper = kc[kcu_col]

    entries = (df["close"] > upper) & (df["close"].shift(1) <= upper.shift(1))
    exits = (df["close"] < lower) & (df["close"].shift(1) >= lower.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Keltner({p['period']},{p['mult']})")]


def get_all_trend_signals(df: pd.DataFrame) -> list[tuple]:
    """汇总所有趋势类指标信号"""
    all_signals = []
    all_signals.extend(ma_crossover_signals(df))
    all_signals.extend(ema_crossover_signals(df))
    all_signals.extend(macd_signals(df))
    all_signals.extend(dmi_adx_signals(df))
    all_signals.extend(aroon_signals(df))
    all_signals.extend(donchian_signals(df))
    all_signals.extend(bollinger_signals(df))
    all_signals.extend(keltner_signals(df))
    return all_signals
