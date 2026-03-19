"""
ETF技术指标策略全面回测系统 — 主入口
===================================
三阶段回测流程:
  阶段一: 单一指标测试（全部）
  阶段二: 两指标组合测试（择优）
  阶段三: 参数优化（最优策略）

运行方式:
  python main.py
"""

import sys
import os
import time
import itertools
import warnings

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# 确保项目根目录在 sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import (
    ETF_SYMBOL, BENCHMARK_SYMBOL, ETF_NAME, BENCHMARK_NAME,
    START_DATE, END_DATE, INIT_CASH, OUTPUT_DIR,
    PHASE2_MIN_SHARPE, PHASE2_MAX_DRAWDOWN, PHASE2_MIN_ANNUAL_RETURN, PHASE2_MIN_TRADES,
    FINAL_MIN_SHARPE, FINAL_MAX_DRAWDOWN, FINAL_MIN_TRADES,
    PARAM_SCAN_RANGE, PARAM_SCAN_STEP,
    INDICATOR_PARAMS,
)
from data.fetcher import load_all_data
from indicators import get_all_indicators
from engine.backtester import run_single_backtest, run_combination_backtest
from engine.metrics import (
    calculate_core_metrics, calculate_aux_metrics,
    calculate_benchmark_metrics, get_monthly_returns, get_trade_log,
)
from reports.tables import (
    generate_phase1_report, generate_phase2_report,
    generate_best_strategy_report, generate_param_sensitivity_report,
    generate_final_recommendation,
)
from reports.charts import (
    plot_equity_curve, plot_drawdown, plot_monthly_heatmap,
    plot_parameter_sensitivity, plot_phase1_overview,
)


# ================================================================
# 阶段一：单一指标测试
# ================================================================
def phase1_single_indicator_test(
    etf_df: pd.DataFrame, benchmark_df: pd.DataFrame
) -> tuple[pd.DataFrame, list[tuple]]:
    """
    运行所有单指标策略，返回排名结果和原始信号。

    Returns:
        (results_df, signals_list)
        signals_list 用于阶段二组合
    """
    print("\n" + "█" * 80)
    print("阶段一：单一指标测试")
    print("█" * 80)

    close = etf_df["close"]

    # 生成所有指标信号
    print("\n[指标生成中...]")
    all_signals = get_all_indicators(etf_df)

    # 逐一回测
    print(f"\n[开始回测 {len(all_signals)} 个策略...]")
    metrics_list = []
    valid_signals = []

    for i, (entries, exits, name) in enumerate(all_signals):
        try:
            pf = run_single_backtest(close, entries, exits)
            m = calculate_core_metrics(pf, name)
            metrics_list.append(m)
            valid_signals.append((entries, exits, name))
            status = f"✓ 夏普={m['夏普比率']:.2f}"
        except Exception as e:
            status = f"✗ {e}"
        print(f"  [{i+1}/{len(all_signals)}] {name}: {status}")

    # 生成报告
    results_df = generate_phase1_report(metrics_list)

    # 绘制概览散点图
    if len(results_df) > 0:
        plot_phase1_overview(results_df)

    return results_df, valid_signals


# ================================================================
# 阶段二：两指标组合测试
# ================================================================
def phase2_combination_test(
    etf_df: pd.DataFrame,
    phase1_df: pd.DataFrame,
    all_signals: list[tuple],
    top_n: int = 10,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    取Phase1 TOP N指标进行两两组合测试。

    Returns:
        (filtered_df, raw_combo_results)
    """
    print("\n" + "█" * 80)
    print("阶段二：两指标组合测试")
    print("█" * 80)

    close = etf_df["close"]

    # 取TOP N
    top_names = phase1_df.head(top_n)["指标名称"].tolist()
    print(f"\nTOP {top_n} 指标: {', '.join(top_names)}")

    # 建立名称到信号的映射
    signal_map = {name: (entries, exits) for entries, exits, name in all_signals}
    top_signals = {n: signal_map[n] for n in top_names if n in signal_map}

    if len(top_signals) < 2:
        print("  TOP指标数不足2个，跳过组合测试")
        return pd.DataFrame(), []

    # 两两组合 × AND/OR
    combos = list(itertools.combinations(top_signals.keys(), 2))
    logics = ["AND", "OR"]
    total = len(combos) * len(logics)
    print(f"  组合数: {len(combos)} × 2(AND/OR) = {total}")

    combo_results = []
    for idx, ((name1, name2), logic) in enumerate(
        itertools.product(combos, logics)
    ):
        combo_name = f"{name1} + {name2}"
        entries1, exits1 = top_signals[name1]
        entries2, exits2 = top_signals[name2]

        try:
            pf = run_combination_backtest(
                close, entries1, exits1, entries2, exits2, logic=logic
            )
            m = calculate_core_metrics(pf, combo_name)
            m["指标组合"] = combo_name
            m["逻辑"] = logic
            combo_results.append(m)
        except Exception as e:
            print(f"  [{idx+1}/{total}] {combo_name} ({logic}): ✗ {e}")
            continue

        if (idx + 1) % 20 == 0 or idx + 1 == total:
            print(f"  已完成 {idx+1}/{total}")

    # 筛选
    all_combo_df = pd.DataFrame(combo_results)
    if all_combo_df.empty:
        print("  无组合回测结果")
        return pd.DataFrame(), combo_results

    filtered = all_combo_df[
        (all_combo_df["夏普比率"] >= PHASE2_MIN_SHARPE)
        & (all_combo_df["最大回撤"] <= PHASE2_MAX_DRAWDOWN * 100)
        & (all_combo_df["年化收益率"] >= PHASE2_MIN_ANNUAL_RETURN * 100)
        & (all_combo_df["交易次数"] >= PHASE2_MIN_TRADES)
    ].copy()

    print(f"\n  筛选前: {len(all_combo_df)} 个组合")
    print(f"  筛选后: {len(filtered)} 个组合 (夏普≥{PHASE2_MIN_SHARPE}, 回撤≤{PHASE2_MAX_DRAWDOWN*100}%)")

    # 报告
    if not filtered.empty:
        generate_phase2_report(filtered.to_dict("records"))
    else:
        # 即使无满足严格条件的组合，也输出TOP5
        print("  无满足严格条件的组合，输出TOP5:")
        top5 = all_combo_df.nlargest(5, "夏普比率")
        generate_phase2_report(top5.to_dict("records"))
        filtered = top5

    # 同时保存全部组合结果
    all_path = os.path.join(OUTPUT_DIR, "phase2_all_combinations.csv")
    all_combo_df.to_csv(all_path, index=False, encoding="utf-8-sig")

    return filtered, combo_results


# ================================================================
# 阶段三：参数优化
# ================================================================
def phase3_parameter_optimization(
    etf_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    best_strategy_name: str,
    all_signals: list[tuple],
) -> pd.DataFrame:
    """
    对最优策略进行参数敏感性分析。
    识别策略使用的指标并扫描其参数。
    """
    print("\n" + "█" * 80)
    print("阶段三：参数优化")
    print("█" * 80)

    close = etf_df["close"]

    # 解析策略名称中的参数
    # 处理单指标和组合指标
    if " + " in best_strategy_name:
        # 组合策略 — 对第一个指标做参数优化
        parts = best_strategy_name.split(" + ")
        target_name = parts[0].strip()
    else:
        target_name = best_strategy_name

    print(f"\n  目标指标: {target_name}")

    # 根据指标名称映射到参数空间
    param_results = _scan_indicator_params(etf_df, close, target_name)

    if not param_results.empty:
        generate_param_sensitivity_report(param_results, target_name)

        # 找到参数列（非指标列）
        metric_cols = {"指标名称", "总收益率", "年化收益率", "最大回撤", "年化波动率",
                      "夏普比率", "卡玛比率", "索提诺比率", "胜率", "盈亏比",
                      "交易次数", "平均持仓天数", "年化交易频率"}
        param_cols = [c for c in param_results.columns if c not in metric_cols]
        if param_cols:
            plot_parameter_sensitivity(param_results, param_cols[0],
                                       strategy_name=target_name)

    return param_results


def _scan_indicator_params(
    df: pd.DataFrame, close: pd.Series, name: str
) -> pd.DataFrame:
    """根据指标名称扫描参数范围"""
    import re
    from indicators.trend import ma_crossover_signals, ema_crossover_signals
    from indicators.momentum import rsi_signals

    results = []

    # MA 系列
    ma_match = re.match(r"MA\((\d+),(\d+)\)", name)
    if ma_match:
        fast_base, slow_base = int(ma_match.group(1)), int(ma_match.group(2))
        for fast_mult in np.arange(1 - PARAM_SCAN_RANGE, 1 + PARAM_SCAN_RANGE + 0.01, PARAM_SCAN_STEP):
            for slow_mult in np.arange(1 - PARAM_SCAN_RANGE, 1 + PARAM_SCAN_RANGE + 0.01, PARAM_SCAN_STEP):
                fast = max(2, int(fast_base * fast_mult))
                slow = max(fast + 1, int(slow_base * slow_mult))
                try:
                    from pandas_ta import sma
                    ma_f = sma(close, length=fast)
                    ma_s = sma(close, length=slow)
                    entries = (ma_f > ma_s) & (ma_f.shift(1) <= ma_s.shift(1))
                    exits = (ma_f < ma_s) & (ma_f.shift(1) >= ma_s.shift(1))
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"MA({fast},{slow})")
                    m["fast"] = fast
                    m["slow"] = slow
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # EMA 系列
    ema_match = re.match(r"EMA\((\d+),(\d+)\)", name)
    if ema_match:
        fast_base, slow_base = int(ema_match.group(1)), int(ema_match.group(2))
        for fast_mult in np.arange(1 - PARAM_SCAN_RANGE, 1 + PARAM_SCAN_RANGE + 0.01, PARAM_SCAN_STEP):
            for slow_mult in np.arange(1 - PARAM_SCAN_RANGE, 1 + PARAM_SCAN_RANGE + 0.01, PARAM_SCAN_STEP):
                fast = max(2, int(fast_base * fast_mult))
                slow = max(fast + 1, int(slow_base * slow_mult))
                try:
                    from pandas_ta import ema
                    ema_f = ema(close, length=fast)
                    ema_s = ema(close, length=slow)
                    entries = (ema_f > ema_s) & (ema_f.shift(1) <= ema_s.shift(1))
                    exits = (ema_f < ema_s) & (ema_f.shift(1) >= ema_s.shift(1))
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"EMA({fast},{slow})")
                    m["fast"] = fast
                    m["slow"] = slow
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # RSI 系列
    rsi_match = re.match(r"RSI\((\d+)\)", name)
    if rsi_match:
        period_base = int(rsi_match.group(1))
        for p_mult in np.arange(1 - PARAM_SCAN_RANGE, 1 + PARAM_SCAN_RANGE + 0.01, PARAM_SCAN_STEP):
            period = max(2, int(period_base * p_mult))
            for buy_t in range(20, 45, 5):
                for sell_t in range(55, 85, 5):
                    try:
                        from pandas_ta import rsi as ta_rsi
                        rsi_val = ta_rsi(close, length=period)
                        entries = (rsi_val < buy_t) & (rsi_val.shift(1) >= buy_t)
                        exits = (rsi_val > sell_t) & (rsi_val.shift(1) <= sell_t)
                        entries = entries.fillna(False)
                        exits = exits.fillna(False)
                        pf = run_single_backtest(close, entries, exits)
                        m = calculate_core_metrics(pf, f"RSI({period},{buy_t},{sell_t})")
                        m["period"] = period
                        m["buy_threshold"] = buy_t
                        m["sell_threshold"] = sell_t
                        results.append(m)
                    except Exception:
                        pass
        return pd.DataFrame(results)

    # MACD 系列
    macd_match = re.match(r"MACD\((\d+),(\d+),(\d+)\)", name)
    if macd_match:
        fast_b, slow_b, sig_b = int(macd_match.group(1)), int(macd_match.group(2)), int(macd_match.group(3))
        for f_m in np.arange(0.6, 1.5, 0.2):
            for s_m in np.arange(0.6, 1.5, 0.2):
                fast = max(2, int(fast_b * f_m))
                slow = max(fast + 1, int(slow_b * s_m))
                signal = sig_b
                try:
                    import pandas_ta as ta
                    macd_df = ta.macd(close, fast=fast, slow=slow, signal=signal)
                    hist_col = [c for c in macd_df.columns if "h" in c.lower() or "hist" in c.lower()][0]
                    hist = macd_df[hist_col]
                    entries = (hist > 0) & (hist.shift(1) <= 0)
                    exits = (hist < 0) & (hist.shift(1) >= 0)
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"MACD({fast},{slow},{signal})")
                    m["fast"] = fast
                    m["slow"] = slow
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # SuperTrend 系列
    st_match = re.match(r"SuperTrend\((\d+),([\d.]+)\)", name)
    if st_match:
        period_b = int(st_match.group(1))
        mult_b = float(st_match.group(2))
        for p_m in np.arange(0.5, 1.55, 0.1):
            for m_m in np.arange(0.5, 1.55, 0.1):
                period = max(2, int(period_b * p_m))
                mult = round(mult_b * m_m, 1)
                try:
                    import pandas_ta as ta
                    st = ta.supertrend(df["high"], df["low"], df["close"],
                                       length=period, multiplier=mult)
                    dir_col = [c for c in st.columns if c.startswith("SUPERTd")][0]
                    direction = st[dir_col]
                    entries = (direction == 1) & (direction.shift(1) == -1)
                    exits = (direction == -1) & (direction.shift(1) == 1)
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"SuperTrend({period},{mult})")
                    m["period"] = period
                    m["multiplier"] = mult
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # SAR 系列
    sar_match = re.match(r"SAR\(([\d.]+),([\d.]+)\)", name)
    if sar_match:
        af_b = float(sar_match.group(1))
        max_af_b = float(sar_match.group(2))
        for af_m in np.arange(0.5, 1.55, 0.1):
            for maf_m in np.arange(0.5, 1.55, 0.1):
                af = round(af_b * af_m, 3)
                max_af = round(max_af_b * maf_m, 2)
                if af >= max_af:
                    continue
                try:
                    import pandas_ta as ta
                    sar = ta.psar(df["high"], df["low"], df["close"],
                                  af0=af, af=af, max_af=max_af)
                    long_col = [c for c in sar.columns if c.startswith("PSARl")][0]
                    short_col = [c for c in sar.columns if c.startswith("PSARs")][0]
                    entries = sar[long_col].notna() & sar[long_col].shift(1).isna()
                    exits = sar[short_col].notna() & sar[short_col].shift(1).isna()
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"SAR({af},{max_af})")
                    m["af"] = af
                    m["max_af"] = max_af
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # Bollinger 系列
    bb_match = re.match(r"Bollinger\((\d+),([\d.]+)\)", name)
    if bb_match:
        period_b = int(bb_match.group(1))
        std_b = float(bb_match.group(2))
        for p_m in np.arange(0.5, 1.55, 0.1):
            for s_m in np.arange(0.5, 1.55, 0.2):
                period = max(5, int(period_b * p_m))
                std = round(std_b * s_m, 1)
                if std < 0.5:
                    continue
                try:
                    import pandas_ta as ta
                    bb = ta.bbands(close, length=period, std=std)
                    bbl = bb[[c for c in bb.columns if c.startswith("BBL")][0]]
                    bbu = bb[[c for c in bb.columns if c.startswith("BBU")][0]]
                    entries = (close <= bbl) & (close.shift(1) > bbl.shift(1))
                    exits = (close >= bbu) & (close.shift(1) < bbu.shift(1))
                    entries = entries.fillna(False)
                    exits = exits.fillna(False)
                    pf = run_single_backtest(close, entries, exits)
                    m = calculate_core_metrics(pf, f"Bollinger({period},{std})")
                    m["period"] = period
                    m["std"] = std
                    results.append(m)
                except Exception:
                    pass
        return pd.DataFrame(results)

    # 通用: 如果无法识别指标，返回空
    print(f"  [警告] 未找到 {name} 的参数优化逻辑，跳过")
    return pd.DataFrame(results)


# ================================================================
# 最优策略详细分析
# ================================================================
def analyze_best_strategy(
    etf_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    best_name: str,
    all_signals: list[tuple],
    combo_info: dict = None,
) -> None:
    """对最优策略生成完整的详细报告和图表"""
    close = etf_df["close"]
    bench_close = benchmark_df["close"]

    # 重新运行最优策略
    if combo_info:
        # 组合策略
        entries1, exits1 = combo_info["signals1"]
        entries2, exits2 = combo_info["signals2"]
        logic = combo_info["logic"]
        pf = run_combination_backtest(close, entries1, exits1, entries2, exits2, logic)
        # 生成合并后的entries用于标注
        entries1 = entries1.reindex(close.index, fill_value=False).astype(bool)
        exits1 = exits1.reindex(close.index, fill_value=False).astype(bool)
        entries2 = entries2.reindex(close.index, fill_value=False).astype(bool)
        exits2 = exits2.reindex(close.index, fill_value=False).astype(bool)
        if logic == "AND":
            final_entries = entries1 & entries2
            final_exits = exits1 | exits2
        else:
            final_entries = entries1 | entries2
            final_exits = exits1 & exits2
    else:
        # 单指标策略
        signal = next((e, x, n) for e, x, n in all_signals if n == best_name)
        entries, exits = signal[0], signal[1]
        pf = run_single_backtest(close, entries, exits)
        final_entries = entries.reindex(close.index, fill_value=False).astype(bool)
        final_exits = exits.reindex(close.index, fill_value=False).astype(bool)

    # 计算指标
    core = calculate_core_metrics(pf, best_name)
    aux = calculate_aux_metrics(pf)
    bench_metrics = calculate_benchmark_metrics(bench_close)
    monthly = get_monthly_returns(pf)
    trades = get_trade_log(pf)

    # 文字报告
    generate_best_strategy_report(core, aux, bench_metrics, monthly, trades)

    # 图表
    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]

    entry_dates = final_entries[final_entries].index
    exit_dates = final_exits[final_exits].index

    plot_equity_curve(equity, bench_close, best_name,
                      entries_idx=entry_dates, exits_idx=exit_dates,
                      filename="best_equity_curve.png")
    plot_drawdown(equity, bench_close, best_name,
                  filename="best_drawdown.png")
    if monthly is not None and not monthly.empty:
        plot_monthly_heatmap(monthly, best_name, filename="best_monthly_heatmap.png")


# ================================================================
# 最终推荐
# ================================================================
def build_final_recommendations(
    phase1_df: pd.DataFrame,
    phase2_df: pd.DataFrame,
    param_df: pd.DataFrame,
    benchmark_metrics: dict,
) -> list[dict]:
    """综合三阶段结果，构建最终推荐"""
    recommendations = []

    # 从Phase1和Phase2中收集候选
    candidates = []

    # Phase1 TOP 5
    if not phase1_df.empty:
        for _, row in phase1_df.head(5).iterrows():
            candidates.append({
                "source": "单指标",
                "name": row["指标名称"],
                "sharpe": row["夏普比率"],
                "annual_return": row["年化收益率"],
                "max_dd": row["最大回撤"],
                "win_rate": row["胜率"],
                "trades": row["交易次数"],
                "profit_loss_ratio": row.get("盈亏比", 0),
            })

    # Phase2 TOP 5
    if not phase2_df.empty:
        for _, row in phase2_df.head(5).iterrows():
            cname = row.get("指标组合", row.get("指标名称", ""))
            logic = row.get("逻辑", "")
            candidates.append({
                "source": f"组合({logic})",
                "name": f"{cname} [{logic}]" if logic else cname,
                "sharpe": row["夏普比率"],
                "annual_return": row["年化收益率"],
                "max_dd": row["最大回撤"],
                "win_rate": row["胜率"],
                "trades": row["交易次数"],
                "profit_loss_ratio": row.get("盈亏比", 0),
            })

    # 去重并排序
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c["name"] not in seen:
            seen.add(c["name"])
            unique_candidates.append(c)

    # 综合评分 = 0.35*夏普 + 0.25*卡玛 + 0.2*胜率/100 + 0.2*盈亏比
    for c in unique_candidates:
        calmar = c["annual_return"] / c["max_dd"] if c["max_dd"] > 0 else 0
        c["score"] = (
            0.35 * c["sharpe"]
            + 0.25 * calmar
            + 0.2 * c["win_rate"] / 100
            + 0.2 * min(c["profit_loss_ratio"], 5) / 5  # 盈亏比上限5归一化
        )

    # 排序取TOP 5
    unique_candidates.sort(key=lambda x: x["score"], reverse=True)
    top = unique_candidates[:5]

    # 构建推荐
    bench_ret = benchmark_metrics.get("基准年化收益率", 0)

    for c in top:
        # 参数敏感性范围
        param_range = None
        if not param_df.empty and "夏普比率" in param_df.columns:
            sharpe_min = param_df["夏普比率"].min()
            sharpe_max = param_df["夏普比率"].max()
            param_range = f"{sharpe_min:.2f} ~ {sharpe_max:.2f}"

        # 策略描述
        if "MA" in c["name"] or "EMA" in c["name"]:
            desc = "均线交叉趋势跟踪策略，适合中长期趋势行情"
            scenario = "趋势明确的牛市/熊市"
            improvement = "可结合成交量过滤假突破，或配合ATR动态止损"
        elif "RSI" in c["name"] or "CCI" in c["name"] or "KDJ" in c["name"]:
            desc = "动量反转策略，适合震荡市中的超买超卖捕捉"
            scenario = "区间震荡市场"
            improvement = "可增加趋势过滤器避免趋势市中逆向交易"
        elif "MACD" in c["name"] or "PPO" in c["name"]:
            desc = "趋势动量策略，捕捉动量转折"
            scenario = "趋势启动初期"
            improvement = "可结合均线确认趋势方向，过滤震荡期虚假信号"
        elif "Super" in c["name"] or "SAR" in c["name"]:
            desc = "趋势跟踪翻转策略，始终保持方向性头寸"
            scenario = "趋势持续明确的市场"
            improvement = "震荡市中可配合波动率过滤器减少频繁翻转"
        elif "Bollinger" in c["name"] or "KC" in c["name"]:
            desc = "通道突破/回归策略"
            scenario = "波动率有规律变化的市场"
            improvement = "可动态调整通道宽度适应不同波动率环境"
        else:
            desc = "技术指标策略"
            scenario = "综合市场环境"
            improvement = "可结合基本面或宏观因子进行过滤"

        recommendations.append({
            "name": c["name"],
            "description": desc,
            "params": c["name"],
            "annual_return": c["annual_return"],
            "sharpe": c["sharpe"],
            "max_dd": c["max_dd"],
            "win_rate": c["win_rate"],
            "trades": c["trades"],
            "param_range": param_range,
            "scenario": scenario,
            "risk": f"最大回撤可达{c['max_dd']}%，过去表现不代表未来收益",
            "improvement": improvement,
        })

    return recommendations


# ================================================================
# MAIN
# ================================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start_time = time.time()

    print("=" * 80)
    print("ETF技术指标策略全面回测系统")
    print(f"标的: {ETF_SYMBOL} ({ETF_NAME})")
    print(f"基准: {BENCHMARK_SYMBOL} ({BENCHMARK_NAME})")
    print(f"周期: {START_DATE} ~ {END_DATE}")
    print(f"初始资金: {INIT_CASH:,.0f} 元")
    print("=" * 80)

    # ---- 数据加载 ----
    print("\n[1/5] 加载数据...")
    etf_df, benchmark_df = load_all_data()
    print(f"  ETF数据: {len(etf_df)} 条 ({etf_df.index[0].date()} ~ {etf_df.index[-1].date()})")
    print(f"  基准数据: {len(benchmark_df)} 条")

    # ---- 基准指标 ----
    bench_metrics = calculate_benchmark_metrics(benchmark_df["close"])
    print(f"  基准年化收益: {bench_metrics['基准年化收益率']}%")
    print(f"  基准最大回撤: {bench_metrics['基准最大回撤']}%")

    # ---- 阶段一 ----
    print("\n[2/5] 阶段一：单一指标测试...")
    phase1_df, all_signals = phase1_single_indicator_test(etf_df, benchmark_df)

    if phase1_df.empty:
        print("\n[错误] 阶段一无有效结果，终止。")
        return

    # ---- 阶段二 ----
    print("\n[3/5] 阶段二：两指标组合测试...")
    phase2_df, combo_results = phase2_combination_test(
        etf_df, phase1_df, all_signals
    )

    # ---- 确定最优策略 ----
    # 优先选组合策略（如果有满足条件的），否则选单指标
    if not phase2_df.empty:
        best_row = phase2_df.iloc[0]
        best_name = best_row.get("指标组合", best_row.get("指标名称", ""))
        best_logic = best_row.get("逻辑", "")
        if best_logic:
            best_display = f"{best_name} [{best_logic}]"
        else:
            best_display = best_name
    else:
        best_row = phase1_df.iloc[0]
        best_name = best_row["指标名称"]
        best_display = best_name
        best_logic = ""

    print(f"\n  >>> 最优策略: {best_display}")

    # ---- 阶段三 ----
    print("\n[4/5] 阶段三：参数优化...")
    # 对最优单指标（或组合中的第一个指标）进行参数优化
    opt_target = best_name.split(" + ")[0].strip() if " + " in best_name else best_name
    param_df = phase3_parameter_optimization(etf_df, benchmark_df, opt_target, all_signals)

    # ---- 最优策略详细分析 ----
    print("\n[5/5] 生成最优策略详细报告...")

    # 构建组合信号信息
    signal_map = {name: (entries, exits) for entries, exits, name in all_signals}
    combo_info = None
    if " + " in best_name and best_logic:
        parts = best_name.split(" + ")
        n1, n2 = parts[0].strip(), parts[1].strip()
        if n1 in signal_map and n2 in signal_map:
            combo_info = {
                "signals1": signal_map[n1],
                "signals2": signal_map[n2],
                "logic": best_logic,
            }

    analyze_name = best_display if combo_info else best_name
    analyze_best_strategy(etf_df, benchmark_df, analyze_name, all_signals, combo_info)

    # ---- 最终推荐 ----
    print("\n[推荐] 构建最终策略推荐...")
    recommendations = build_final_recommendations(phase1_df, phase2_df, param_df, bench_metrics)
    generate_final_recommendation(recommendations)

    # ---- 完成 ----
    elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"回测完成！耗时 {elapsed:.1f} 秒")
    print(f"所有报告和图表已保存至: {os.path.abspath(OUTPUT_DIR)}/")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
