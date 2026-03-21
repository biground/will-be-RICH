"""
动量类技术指标信号生成
每个函数返回列表 [(entries, exits, name), ...]
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from config import INDICATOR_PARAMS


def rsi_signals(df: pd.DataFrame) -> list[tuple]:
    """RSI 超卖买入/超买卖出"""
    results = []
    close = df["close"]
    buy_thresh = INDICATOR_PARAMS["rsi_buy"]
    sell_thresh = INDICATOR_PARAMS["rsi_sell"]
    for period in INDICATOR_PARAMS["rsi_periods"]:
        rsi = ta.rsi(close, length=period)
        # 从超卖区向上穿越买入，从超买区向下穿越卖出
        entries = (rsi > buy_thresh) & (rsi.shift(1) <= buy_thresh)
        exits = (rsi < sell_thresh) & (rsi.shift(1) >= sell_thresh)
        entries = entries.fillna(False)
        exits = exits.fillna(False)
        results.append((entries, exits, f"RSI({period})"))
    return results


def kdj_signals(df: pd.DataFrame) -> list[tuple]:
    """KDJ 随机指标: K线上穿D线买入，下穿卖出"""
    p = INDICATOR_PARAMS["kdj"]
    stoch = ta.stoch(
        df["high"], df["low"], df["close"],
        k=p["k_period"], d=p["d_period"], smooth_k=p["j_period"],
    )
    k_col = [c for c in stoch.columns if c.startswith("STOCHk")][0]
    d_col = [c for c in stoch.columns if c.startswith("STOCHd")][0]
    k_line = stoch[k_col]
    d_line = stoch[d_col]

    entries = (k_line > d_line) & (k_line.shift(1) <= d_line.shift(1)) & (k_line < 30)
    exits = (k_line < d_line) & (k_line.shift(1) >= d_line.shift(1)) & (k_line > 70)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"KDJ({p['k_period']},{p['d_period']},{p['j_period']})")]


def cci_signals(df: pd.DataFrame) -> list[tuple]:
    """CCI: <-100买入，>100卖出"""
    results = []
    buy_thresh = INDICATOR_PARAMS["cci_buy"]
    sell_thresh = INDICATOR_PARAMS["cci_sell"]
    for period in INDICATOR_PARAMS["cci_periods"]:
        cci = ta.cci(df["high"], df["low"], df["close"], length=period)
        entries = (cci > buy_thresh) & (cci.shift(1) <= buy_thresh)
        exits = (cci < sell_thresh) & (cci.shift(1) >= sell_thresh)
        entries = entries.fillna(False)
        exits = exits.fillna(False)
        results.append((entries, exits, f"CCI({period})"))
    return results


def roc_signals(df: pd.DataFrame) -> list[tuple]:
    """ROC 变动率: 由负转正买入，由正转负卖出"""
    p = INDICATOR_PARAMS["roc"]
    roc = ta.roc(df["close"], length=p["period"])
    entries = (roc > 0) & (roc.shift(1) <= 0)
    exits = (roc < 0) & (roc.shift(1) >= 0)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"ROC({p['period']})")]


def mtm_signals(df: pd.DataFrame) -> list[tuple]:
    """MTM 动量线: 由负转正买入，由正转负卖出"""
    p = INDICATOR_PARAMS["mtm"]
    # MTM = close - close[n]
    mtm = df["close"] - df["close"].shift(p["period"])
    entries = (mtm > 0) & (mtm.shift(1) <= 0)
    exits = (mtm < 0) & (mtm.shift(1) >= 0)
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"MTM({p['period']})")]


def williams_r_signals(df: pd.DataFrame) -> list[tuple]:
    """Williams %R: <买入阈值买入，>卖出阈值卖出"""
    p = INDICATOR_PARAMS["williams_r"]
    wr = ta.willr(df["high"], df["low"], df["close"], length=p["period"])
    entries = (wr > p["buy"]) & (wr.shift(1) <= p["buy"])
    exits = (wr < p["sell"]) & (wr.shift(1) >= p["sell"])
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"Williams%R({p['period']})")]


def cmo_signals(df: pd.DataFrame) -> list[tuple]:
    """CMO 钱德动量: <买入阈值买入，>卖出阈值卖出"""
    p = INDICATOR_PARAMS["cmo"]
    cmo = ta.cmo(df["close"], length=p["period"])
    entries = (cmo > p["buy"]) & (cmo.shift(1) <= p["buy"])
    exits = (cmo < p["sell"]) & (cmo.shift(1) >= p["sell"])
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"CMO({p['period']})")]


def ppo_signals(df: pd.DataFrame) -> list[tuple]:
    """PPO: PPO上穿信号线买入，下穿卖出"""
    p = INDICATOR_PARAMS["ppo"]
    ppo_df = ta.ppo(df["close"], fast=p["fast"], slow=p["slow"], signal=p["signal"])
    ppo_col = [c for c in ppo_df.columns if "PPO_" in c and "H" not in c and "S" not in c][0]
    sig_col = [c for c in ppo_df.columns if "PPOs_" in c or "S" in c][0]
    ppo_line = ppo_df[ppo_col]
    sig_line = ppo_df[sig_col]

    entries = (ppo_line > sig_line) & (ppo_line.shift(1) <= sig_line.shift(1))
    exits = (ppo_line < sig_line) & (ppo_line.shift(1) >= sig_line.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"PPO({p['fast']},{p['slow']},{p['signal']})")]


def get_all_momentum_signals(df: pd.DataFrame) -> list[tuple]:
    """汇总所有动量类指标信号"""
    all_signals = []
    all_signals.extend(rsi_signals(df))
    all_signals.extend(kdj_signals(df))
    all_signals.extend(cci_signals(df))
    all_signals.extend(roc_signals(df))
    all_signals.extend(mtm_signals(df))
    all_signals.extend(williams_r_signals(df))
    all_signals.extend(cmo_signals(df))
    all_signals.extend(ppo_signals(df))
    return all_signals
