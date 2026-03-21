"""
信号解释引擎 — 将技术指标的原始 entries/exits 信号
转化为面向散户的 "买入 / 卖出 / 持有" 决策建议。
"""

import pandas as pd
import numpy as np
from indicators import get_all_indicators


# ------------------------------------------------------------------
# 核心：获取每个指标的当前信号
# ------------------------------------------------------------------
def get_current_signals(df: pd.DataFrame) -> list[dict]:
    """
    对 OHLCV DataFrame 计算所有指标，取最后一个交易日的信号状态。

    Returns
    -------
    list[dict]  每个元素:
        {
            "name":        指标名称,
            "signal":      "买入" | "卖出" | "持有",
            "strength":    0-100 信号强度（简化：买入/卖出=80, 持有=50）,
            "description": 面向用户的一句话描述,
        }
    """
    all_signals = get_all_indicators(df)
    results = []

    for entries, exits, name in all_signals:
        try:
            entries = entries.reindex(df.index, fill_value=False).astype(bool)
            exits = exits.reindex(df.index, fill_value=False).astype(bool)

            last_entry = bool(entries.iloc[-1]) if len(entries) > 0 else False
            last_exit = bool(exits.iloc[-1]) if len(exits) > 0 else False

            if last_entry and not last_exit:
                signal = "买入"
                strength = 80
                desc = f"{name} 发出买入信号"
            elif last_exit and not last_entry:
                signal = "卖出"
                strength = 80
                desc = f"{name} 发出卖出信号"
            else:
                # 无新信号 — 判断当前是否处于持仓状态
                signal = "持有"
                strength = 50
                desc = f"{name} 暂无新信号"

            results.append({
                "name": name,
                "signal": signal,
                "strength": strength,
                "description": desc,
            })
        except Exception:
            continue

    return results


# ------------------------------------------------------------------
# 综合投票：给出整体决策建议
# ------------------------------------------------------------------
def get_consensus_signal(signals: list[dict]) -> dict:
    """
    综合所有指标信号进行投票，返回整体建议。

    Returns
    -------
    dict:
        {
            "action":     "买入" | "卖出" | "观望",
            "confidence": 0-100,
            "buy_count":  int,
            "sell_count": int,
            "hold_count": int,
            "reason":     一句话理由,
        }
    """
    if not signals:
        return {
            "action": "观望",
            "confidence": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "reason": "无法获取指标数据",
        }

    buy_count = sum(1 for s in signals if s["signal"] == "买入")
    sell_count = sum(1 for s in signals if s["signal"] == "卖出")
    hold_count = sum(1 for s in signals if s["signal"] == "持有")
    total = len(signals)

    buy_pct = buy_count / total * 100
    sell_pct = sell_count / total * 100

    # 决策阈值：≥40% 一致才给出明确建议
    if buy_pct >= 40 and buy_pct > sell_pct:
        action = "买入"
        confidence = min(int(buy_pct), 95)
        reason = f"{buy_count}/{total} 个指标发出买入信号，多头占优"
    elif sell_pct >= 40 and sell_pct > buy_pct:
        action = "卖出"
        confidence = min(int(sell_pct), 95)
        reason = f"{sell_count}/{total} 个指标发出卖出信号，空头占优"
    else:
        action = "观望"
        confidence = max(int(100 - buy_pct - sell_pct), 30)
        reason = f"指标信号分歧较大（买入{buy_count}/卖出{sell_count}/持有{hold_count}），建议观望"

    return {
        "action": action,
        "confidence": confidence,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "reason": reason,
    }


# ------------------------------------------------------------------
# 市场状态判断
# ------------------------------------------------------------------
def classify_market_state(df: pd.DataFrame) -> dict:
    """
    基于均线排列 + 波动率判断当前市场状态。

    Returns
    -------
    dict:
        {
            "state":       "上升趋势" | "下降趋势" | "震荡市",
            "description": 面向用户的描述,
            "color":       "#10B981" | "#EF4444" | "#F59E0B",
            "icon":        "📈" | "📉" | "↔️",
        }
    """
    close = df["close"]
    if len(close) < 60:
        return {
            "state": "数据不足",
            "description": "历史数据不足 60 个交易日，无法判断市场状态",
            "color": "#6B7280",
            "icon": "❓",
        }

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    current_price = float(close.iloc[-1])
    current_ma20 = float(ma20.iloc[-1])
    current_ma60 = float(ma60.iloc[-1])

    # 20日波动率
    daily_ret = close.pct_change().dropna()
    vol_20 = float(daily_ret.tail(20).std()) * np.sqrt(252) * 100  # 年化 %

    if current_price > current_ma20 > current_ma60:
        state = "上升趋势"
        desc = f"价格在 20 日和 60 日均线之上，均线多头排列，年化波动率 {vol_20:.1f}%"
        color = "#10B981"
        icon = "📈"
    elif current_price < current_ma20 < current_ma60:
        state = "下降趋势"
        desc = f"价格在 20 日和 60 日均线之下，均线空头排列，年化波动率 {vol_20:.1f}%"
        color = "#EF4444"
        icon = "📉"
    else:
        state = "震荡市"
        desc = f"均线交错，价格方向不明确，年化波动率 {vol_20:.1f}%"
        color = "#F59E0B"
        icon = "↔️"

    return {
        "state": state,
        "description": desc,
        "color": color,
        "icon": icon,
    }


# ------------------------------------------------------------------
# 信号分类汇总（用于 UI 展示）
# ------------------------------------------------------------------
def get_signal_summary(signals: list[dict]) -> dict:
    """
    将信号按买入/卖出/持有分组，方便 UI 渲染。

    Returns
    -------
    dict:  {"buy": [...], "sell": [...], "hold": [...]}
    """
    return {
        "buy":  [s for s in signals if s["signal"] == "买入"],
        "sell": [s for s in signals if s["signal"] == "卖出"],
        "hold": [s for s in signals if s["signal"] == "持有"],
    }
