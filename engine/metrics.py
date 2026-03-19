"""
绩效指标计算模块 — 从 VectorBT Portfolio 提取核心与辅助指标
"""

import pandas as pd
import numpy as np
from scipy import stats as sp_stats
import vectorbt as vbt

from config import RISK_FREE_RATE


def calculate_core_metrics(pf: vbt.Portfolio, name: str = "") -> dict:
    """
    计算核心绩效指标。

    Returns:
        dict 包含所有核心指标
    """
    # 基础数据
    total_return = pf.total_return()
    if isinstance(total_return, pd.Series):
        total_return = total_return.iloc[0]

    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]
    daily_returns = equity.pct_change().dropna()

    trading_days = len(equity)
    years = trading_days / 252

    # --- 收益指标 ---
    annual_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1

    # --- 风险指标 ---
    max_dd = pf.max_drawdown()
    if isinstance(max_dd, pd.Series):
        max_dd = max_dd.iloc[0]
    max_dd = abs(max_dd)

    annual_vol = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0.0

    # --- 风险调整指标 ---
    sharpe = (annual_return - RISK_FREE_RATE) / annual_vol if annual_vol > 0 else 0.0
    calmar = annual_return / max_dd if max_dd > 0 else 0.0

    # 索提诺比率 (下行波动率)
    down_returns = daily_returns[daily_returns < 0]
    downside_vol = down_returns.std() * np.sqrt(252) if len(down_returns) > 1 else 0.0
    sortino = (annual_return - RISK_FREE_RATE) / downside_vol if downside_vol > 0 else 0.0

    # --- 交易统计 ---
    trades = pf.trades.records_readable if hasattr(pf.trades, 'records_readable') else pd.DataFrame()
    n_trades = len(trades) if len(trades) > 0 else 0

    if n_trades > 0:
        if "PnL" in trades.columns:
            pnl_col = "PnL"
        elif "pnl" in trades.columns:
            pnl_col = "pnl"
        else:
            pnl_col = None

        if pnl_col:
            winning = trades[trades[pnl_col] > 0]
            losing = trades[trades[pnl_col] < 0]
            win_rate = len(winning) / n_trades if n_trades > 0 else 0.0
            avg_win = winning[pnl_col].mean() if len(winning) > 0 else 0.0
            avg_loss = abs(losing[pnl_col].mean()) if len(losing) > 0 else 0.0
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
        else:
            win_rate = 0.0
            profit_loss_ratio = 0.0
    else:
        win_rate = 0.0
        profit_loss_ratio = 0.0

    # 平均持仓天数
    if n_trades > 0 and "Duration" in trades.columns:
        avg_hold = trades["Duration"].mean()
        if hasattr(avg_hold, 'days'):
            avg_hold_days = avg_hold.days
        else:
            avg_hold_days = float(avg_hold)
    else:
        avg_hold_days = 0.0

    annual_trade_freq = n_trades / years if years > 0 else 0.0

    return {
        "指标名称": name,
        "总收益率": round(total_return * 100, 2),
        "年化收益率": round(annual_return * 100, 2),
        "最大回撤": round(max_dd * 100, 2),
        "年化波动率": round(annual_vol * 100, 2),
        "夏普比率": round(sharpe, 3),
        "卡玛比率": round(calmar, 3),
        "索提诺比率": round(sortino, 3),
        "胜率": round(win_rate * 100, 2),
        "盈亏比": round(profit_loss_ratio, 3),
        "交易次数": n_trades,
        "平均持仓天数": round(avg_hold_days, 1),
        "年化交易频率": round(annual_trade_freq, 1),
    }


def calculate_aux_metrics(pf: vbt.Portfolio) -> dict:
    """计算辅助绩效指标"""
    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]
    daily_returns = equity.pct_change().dropna()

    trades = pf.trades.records_readable if hasattr(pf.trades, 'records_readable') else pd.DataFrame()

    # 盈利因子
    if len(trades) > 0:
        pnl_col = "PnL" if "PnL" in trades.columns else ("pnl" if "pnl" in trades.columns else None)
        if pnl_col:
            gross_profit = trades[trades[pnl_col] > 0][pnl_col].sum()
            gross_loss = abs(trades[trades[pnl_col] < 0][pnl_col].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            expected_return = trades[pnl_col].mean()
        else:
            profit_factor = 0.0
            expected_return = 0.0
    else:
        profit_factor = 0.0
        expected_return = 0.0

    # 分布统计
    if len(daily_returns) > 3:
        skewness = sp_stats.skew(daily_returns)
        kurtosis_val = sp_stats.kurtosis(daily_returns)
        var_95 = np.percentile(daily_returns, 5)
        cvar_95 = daily_returns[daily_returns <= var_95].mean() if len(daily_returns[daily_returns <= var_95]) > 0 else var_95
    else:
        skewness = 0.0
        kurtosis_val = 0.0
        var_95 = 0.0
        cvar_95 = 0.0

    return {
        "盈利因子": round(profit_factor, 3),
        "预期收益": round(expected_return, 2),
        "偏度": round(float(skewness), 3),
        "峰度": round(float(kurtosis_val), 3),
        "VaR_95": round(float(var_95) * 100, 3),
        "CVaR_95": round(float(cvar_95) * 100, 3),
    }


def calculate_benchmark_metrics(benchmark_close: pd.Series) -> dict:
    """计算基准收益指标"""
    total_return = (benchmark_close.iloc[-1] / benchmark_close.iloc[0]) - 1
    trading_days = len(benchmark_close)
    years = trading_days / 252
    annual_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1

    daily_returns = benchmark_close.pct_change().dropna()
    annual_vol = daily_returns.std() * np.sqrt(252)

    # 最大回撤
    cummax = benchmark_close.cummax()
    drawdown = (benchmark_close - cummax) / cummax
    max_dd = abs(drawdown.min())

    sharpe = (annual_return - RISK_FREE_RATE) / annual_vol if annual_vol > 0 else 0.0

    return {
        "基准总收益率": round(total_return * 100, 2),
        "基准年化收益率": round(annual_return * 100, 2),
        "基准最大回撤": round(max_dd * 100, 2),
        "基准年化波动率": round(annual_vol * 100, 2),
        "基准夏普比率": round(sharpe, 3),
    }


def get_monthly_returns(pf: vbt.Portfolio) -> pd.DataFrame:
    """计算月度收益率表 (年×月)"""
    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]

    monthly = equity.resample("ME").last().pct_change()
    monthly_df = pd.DataFrame({
        "year": monthly.index.year,
        "month": monthly.index.month,
        "return": monthly.values,
    })
    pivot = monthly_df.pivot(index="year", columns="month", values="return")
    pivot.columns = [f"{m}月" for m in pivot.columns]
    # 添加年度汇总
    pivot["全年"] = pivot.apply(lambda row: (1 + row.dropna()).prod() - 1, axis=1)
    return pivot


def get_trade_log(pf: vbt.Portfolio) -> pd.DataFrame:
    """提取交易记录表"""
    trades = pf.trades.records_readable if hasattr(pf.trades, 'records_readable') else pd.DataFrame()
    if len(trades) == 0:
        return pd.DataFrame()

    cols_map = {}
    for old, new in [
        ("Entry Timestamp", "买入时间"), ("Exit Timestamp", "卖出时间"),
        ("Avg Entry Price", "买入价"), ("Avg Exit Price", "卖出价"),
        ("PnL", "盈亏金额"), ("Return", "收益率"), ("Duration", "持仓天数"),
        ("Direction", "方向"), ("Size", "数量"),
    ]:
        if old in trades.columns:
            cols_map[old] = new

    result = trades.rename(columns=cols_map)
    keep = [v for v in cols_map.values() if v in result.columns]
    return result[keep] if keep else result
