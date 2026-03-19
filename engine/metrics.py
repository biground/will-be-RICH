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


# ============================================================
# 专业量化分析扩展函数
# ============================================================

def get_rolling_sharpe(equity: pd.Series, window: int = 60) -> pd.Series:
    """计算滚动夏普比率（年化），展示策略稳定性随时间变化"""
    daily_returns = equity.pct_change().dropna()
    rolling_mean = daily_returns.rolling(window).mean() * 252
    rolling_std = daily_returns.rolling(window).std() * np.sqrt(252)
    rolling_sharpe = (rolling_mean - RISK_FREE_RATE) / rolling_std
    return rolling_sharpe.dropna()


def calculate_strategy_grade(core: dict, aux: dict) -> dict:
    """
    策略综合评级 A/B/C/D/F，基于多维度加权评分。
    返回 {"grade": "A", "score": 85, "dimensions": {...}}
    """
    # 各维度标准化到 0~100
    def _norm(val, lo, hi):
        return max(0.0, min(100.0, (val - lo) / (hi - lo) * 100)) if hi != lo else 50.0

    sharpe = core.get("夏普比率", 0)
    max_dd = core.get("最大回撤", 0)
    win_rate = core.get("胜率", 0)
    plr = core.get("盈亏比", 0)
    pf = aux.get("盈利因子", 0)
    calmar = core.get("卡玛比率", 0)

    dims = {
        "收益风险比": _norm(sharpe, -0.5, 3.0),
        "回撤控制": _norm(50 - max_dd, -20, 50),       # 回撤越小分越高
        "胜率": _norm(win_rate, 20, 80),
        "盈亏比": _norm(min(plr, 5), 0, 5),
        "盈利因子": _norm(min(pf, 5), 0, 5),
        "卡玛比率": _norm(calmar, -0.5, 3.0),
    }

    weights = {"收益风险比": 0.25, "回撤控制": 0.20, "胜率": 0.15,
               "盈亏比": 0.15, "盈利因子": 0.15, "卡玛比率": 0.10}
    score = sum(dims[k] * weights[k] for k in dims)

    if score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 45:
        grade = "C"
    elif score >= 25:
        grade = "D"
    else:
        grade = "F"

    return {"grade": grade, "score": round(score, 1), "dimensions": dims}


def get_streak_stats(trade_log_df: pd.DataFrame) -> dict:
    """计算最大连续盈利/亏损次数统计"""
    if trade_log_df is None or trade_log_df.empty:
        return {"max_win_streak": 0, "max_loss_streak": 0,
                "avg_win_streak": 0, "avg_loss_streak": 0}

    pnl_col = None
    for col in ["盈亏金额", "PnL", "pnl"]:
        if col in trade_log_df.columns:
            pnl_col = col
            break
    if pnl_col is None:
        return {"max_win_streak": 0, "max_loss_streak": 0,
                "avg_win_streak": 0, "avg_loss_streak": 0}

    pnl = trade_log_df[pnl_col].values
    max_win, max_loss = 0, 0
    cur_win, cur_loss = 0, 0
    win_streaks, loss_streaks = [], []

    for v in pnl:
        if v > 0:
            cur_win += 1
            if cur_loss > 0:
                loss_streaks.append(cur_loss)
                cur_loss = 0
        elif v < 0:
            cur_loss += 1
            if cur_win > 0:
                win_streaks.append(cur_win)
                cur_win = 0
        else:
            if cur_win > 0:
                win_streaks.append(cur_win)
            if cur_loss > 0:
                loss_streaks.append(cur_loss)
            cur_win = cur_loss = 0

    if cur_win > 0:
        win_streaks.append(cur_win)
    if cur_loss > 0:
        loss_streaks.append(cur_loss)

    return {
        "max_win_streak": max(win_streaks) if win_streaks else 0,
        "max_loss_streak": max(loss_streaks) if loss_streaks else 0,
        "avg_win_streak": round(np.mean(win_streaks), 1) if win_streaks else 0,
        "avg_loss_streak": round(np.mean(loss_streaks), 1) if loss_streaks else 0,
    }
