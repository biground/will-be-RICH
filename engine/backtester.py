"""
VectorBT 回测引擎封装
"""

import pandas as pd
import numpy as np
import vectorbt as vbt

from config import INIT_CASH, ENTRY_FEES, EXIT_FEES


def run_single_backtest(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    init_cash: float = INIT_CASH,
    entry_fees: float = ENTRY_FEES,
    exit_fees: float = EXIT_FEES,
) -> vbt.Portfolio:
    """
    运行单个策略回测。

    Args:
        close: 收盘价序列
        entries: 买入信号 (bool Series)
        exits: 卖出信号 (bool Series)
        init_cash: 初始资金
        entry_fees: 买入费率 (滑点+佣金)
        exit_fees: 卖出费率 (滑点+佣金+印花税)

    Returns:
        vbt.Portfolio 对象
    """
    # 确保 entries/exits 与 close 索引一致
    entries = entries.reindex(close.index, fill_value=False).astype(bool)
    exits = exits.reindex(close.index, fill_value=False).astype(bool)

    pf = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=init_cash,
        fees=np.mean([entry_fees, exit_fees]),  # VectorBT 对称费率用均值近似
        slippage=0.0,  # 滑点已包含在fees中
        freq="1D",
        direction="longonly",
        accumulate=False,  # 不累积加仓，满仓进出
    )
    return pf


def run_batch_backtest(
    close: pd.Series,
    signals_list: list[tuple],
    init_cash: float = INIT_CASH,
) -> list[tuple]:
    """
    批量运行多个策略。

    Args:
        close: 收盘价序列
        signals_list: [(entries, exits, name), ...]

    Returns:
        [(portfolio, name), ...]
    """
    results = []
    for entries, exits, name in signals_list:
        try:
            pf = run_single_backtest(close, entries, exits, init_cash=init_cash)
            results.append((pf, name))
        except Exception as e:
            print(f"  [回测失败] {name}: {e}")
    return results


def run_combination_backtest(
    close: pd.Series,
    entries1: pd.Series,
    exits1: pd.Series,
    entries2: pd.Series,
    exits2: pd.Series,
    logic: str = "AND",
    init_cash: float = INIT_CASH,
) -> vbt.Portfolio:
    """
    运行两指标组合回测。

    Args:
        logic: "AND" — 两个指标同时满足才交易
               "OR"  — 任一指标满足即交易
    """
    entries1 = entries1.reindex(close.index, fill_value=False).astype(bool)
    exits1 = exits1.reindex(close.index, fill_value=False).astype(bool)
    entries2 = entries2.reindex(close.index, fill_value=False).astype(bool)
    exits2 = exits2.reindex(close.index, fill_value=False).astype(bool)

    if logic == "AND":
        # 两个都发出买入信号才买入，任一发出卖出信号就卖出
        combined_entries = entries1 & entries2
        combined_exits = exits1 | exits2
    elif logic == "OR":
        # 任一发出买入信号就买入，两个都发出卖出信号才卖出
        combined_entries = entries1 | entries2
        combined_exits = exits1 & exits2
    else:
        raise ValueError(f"不支持的组合逻辑: {logic}")

    return run_single_backtest(close, combined_entries, combined_exits, init_cash=init_cash)
