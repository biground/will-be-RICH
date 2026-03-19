"""
指标注册表 — 统一管理所有技术指标信号生成函数
"""

import pandas as pd
from indicators.trend import get_all_trend_signals
from indicators.momentum import get_all_momentum_signals
from indicators.volume import get_all_volume_signals
from indicators.volatility import get_all_volatility_signals
from indicators.composite import get_all_composite_signals


def get_all_indicators(df: pd.DataFrame) -> list[tuple]:
    """
    获取所有技术指标的买卖信号。

    Args:
        df: OHLCV DataFrame

    Returns:
        list of (entries: pd.Series[bool], exits: pd.Series[bool], name: str)
    """
    all_signals = []

    categories = [
        ("趋势类", get_all_trend_signals),
        ("动量类", get_all_momentum_signals),
        ("成交量类", get_all_volume_signals),
        ("波动率类", get_all_volatility_signals),
        ("综合类", get_all_composite_signals),
    ]

    for cat_name, func in categories:
        try:
            signals = func(df)
            print(f"  [{cat_name}] 生成 {len(signals)} 个信号")
            all_signals.extend(signals)
        except Exception as e:
            print(f"  [{cat_name}] 生成失败: {e}")

    print(f"  共计 {len(all_signals)} 个单指标策略")
    return all_signals
