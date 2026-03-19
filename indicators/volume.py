"""
成交量类技术指标信号生成
每个函数返回列表 [(entries, exits, name), ...]
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from config import INDICATOR_PARAMS


def vwap_signals(df: pd.DataFrame) -> list[tuple]:
    """
    滚动VWAP: 价格上穿滚动VWAP买入，下穿卖出。
    日线级别使用滚动窗口VWAP替代日内VWAP。
    """
    p = INDICATOR_PARAMS["vwap"]
    period = p["period"]
    # 计算滚动VWAP = 累积(典型价格×成交量) / 累积(成交量)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    tp_vol = (typical_price * df["volume"]).rolling(window=period).sum()
    vol_sum = df["volume"].rolling(window=period).sum()
    vwap = tp_vol / vol_sum

    entries = (df["close"] > vwap) & (df["close"].shift(1) <= vwap.shift(1))
    exits = (df["close"] < vwap) & (df["close"].shift(1) >= vwap.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"VWAP({period})")]


def obv_signals(df: pd.DataFrame) -> list[tuple]:
    """OBV 能量潮: OBV上穿其MA买入，下穿卖出"""
    p = INDICATOR_PARAMS["obv_ma"]
    obv = ta.obv(df["close"], df["volume"])
    obv_ma = ta.sma(obv, length=p["period"])

    entries = (obv > obv_ma) & (obv.shift(1) <= obv_ma.shift(1))
    exits = (obv < obv_ma) & (obv.shift(1) >= obv_ma.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"OBV_MA({p['period']})")]


def pvt_signals(df: pd.DataFrame) -> list[tuple]:
    """PVT 价量趋势: PVT上穿其MA买入，下穿卖出"""
    p = INDICATOR_PARAMS["pvt_ma"]
    pvt = ta.pvt(df["close"], df["volume"])
    pvt_ma = ta.sma(pvt, length=p["period"])

    entries = (pvt > pvt_ma) & (pvt.shift(1) <= pvt_ma.shift(1))
    exits = (pvt < pvt_ma) & (pvt.shift(1) >= pvt_ma.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"PVT_MA({p['period']})")]


def mfi_signals(df: pd.DataFrame) -> list[tuple]:
    """MFI 资金流量指标: MFI<阈值买入，MFI>阈值卖出"""
    p = INDICATOR_PARAMS["mfi"]
    mfi = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=p["period"])

    entries = (mfi > p["buy"]) & (mfi.shift(1) <= p["buy"])
    exits = (mfi < p["sell"]) & (mfi.shift(1) >= p["sell"])
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"MFI({p['period']})")]


def ad_signals(df: pd.DataFrame) -> list[tuple]:
    """AD 累积派发指标: AD上穿其MA买入，下穿卖出"""
    p = INDICATOR_PARAMS["ad_ma"]
    ad = ta.ad(df["high"], df["low"], df["close"], df["volume"])
    ad_ma = ta.sma(ad, length=p["period"])

    entries = (ad > ad_ma) & (ad.shift(1) <= ad_ma.shift(1))
    exits = (ad < ad_ma) & (ad.shift(1) >= ad_ma.shift(1))
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"AD_MA({p['period']})")]


def vroc_signals(df: pd.DataFrame) -> list[tuple]:
    """VROC 成交量变动率: VROC由负转正且价格上涨买入，VROC由正转负且价格下跌卖出"""
    p = INDICATOR_PARAMS["vroc"]
    period = p["period"]
    vroc = (df["volume"] - df["volume"].shift(period)) / df["volume"].shift(period) * 100
    price_up = df["close"] > df["close"].shift(1)
    price_dn = df["close"] < df["close"].shift(1)

    entries = (vroc > 0) & (vroc.shift(1) <= 0) & price_up
    exits = (vroc < 0) & (vroc.shift(1) >= 0) & price_dn
    entries = entries.fillna(False)
    exits = exits.fillna(False)
    return [(entries, exits, f"VROC({period})")]


def get_all_volume_signals(df: pd.DataFrame) -> list[tuple]:
    """汇总所有成交量类指标信号"""
    all_signals = []
    all_signals.extend(vwap_signals(df))
    all_signals.extend(obv_signals(df))
    all_signals.extend(pvt_signals(df))
    all_signals.extend(mfi_signals(df))
    all_signals.extend(ad_signals(df))
    all_signals.extend(vroc_signals(df))
    return all_signals
