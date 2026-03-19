"""
图表生成模块 — 收益曲线、回撤、热力图等
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # 无头模式
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

from config import OUTPUT_DIR, ETF_NAME, BENCHMARK_NAME

# 中文字体配置
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_equity_curve(
    strategy_equity: pd.Series,
    benchmark_close: pd.Series,
    strategy_name: str,
    entries_idx: pd.DatetimeIndex = None,
    exits_idx: pd.DatetimeIndex = None,
    filename: str = "equity_curve.png",
) -> str:
    """
    绘制策略收益曲线 vs 基准，可标注买卖点。

    Returns:
        保存路径
    """
    _ensure_output()

    # 归一化为100起点
    strat_norm = strategy_equity / strategy_equity.iloc[0] * 100
    bench_norm = benchmark_close / benchmark_close.iloc[0] * 100

    fig, ax = plt.subplots(figsize=(16, 8))
    ax.plot(strat_norm.index, strat_norm.values, label=f"策略: {strategy_name}",
            color="#1f77b4", linewidth=1.5)
    ax.plot(bench_norm.index, bench_norm.values, label=f"基准: {BENCHMARK_NAME}",
            color="#ff7f0e", linewidth=1.2, alpha=0.7)

    # 标注买卖点
    if entries_idx is not None and len(entries_idx) > 0:
        valid_entries = entries_idx.intersection(strat_norm.index)
        if len(valid_entries) > 0:
            ax.scatter(valid_entries, strat_norm.loc[valid_entries],
                       marker="^", color="red", s=40, zorder=5, label="买入", alpha=0.7)

    if exits_idx is not None and len(exits_idx) > 0:
        valid_exits = exits_idx.intersection(strat_norm.index)
        if len(valid_exits) > 0:
            ax.scatter(valid_exits, strat_norm.loc[valid_exits],
                       marker="v", color="green", s=40, zorder=5, label="卖出", alpha=0.7)

    ax.set_title(f"策略收益曲线: {strategy_name} vs {BENCHMARK_NAME}", fontsize=14)
    ax.set_xlabel("日期")
    ax.set_ylabel("净值（起始=100）")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[图表] 收益曲线已保存: {path}")
    return path


def plot_drawdown(
    strategy_equity: pd.Series,
    benchmark_close: pd.Series,
    strategy_name: str,
    filename: str = "drawdown.png",
) -> str:
    """绘制回撤对比图"""
    _ensure_output()

    def calc_dd(series):
        cummax = series.cummax()
        return (series - cummax) / cummax

    strat_dd = calc_dd(strategy_equity)
    bench_dd = calc_dd(benchmark_close)

    fig, ax = plt.subplots(figsize=(16, 6))
    ax.fill_between(strat_dd.index, strat_dd.values * 100, 0,
                    alpha=0.4, color="#1f77b4", label=f"策略: {strategy_name}")
    ax.fill_between(bench_dd.index, bench_dd.values * 100, 0,
                    alpha=0.3, color="#ff7f0e", label=f"基准: {BENCHMARK_NAME}")

    ax.set_title(f"回撤对比: {strategy_name} vs {BENCHMARK_NAME}", fontsize=14)
    ax.set_xlabel("日期")
    ax.set_ylabel("回撤 (%)")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[图表] 回撤曲线已保存: {path}")
    return path


def plot_monthly_heatmap(
    monthly_returns: pd.DataFrame,
    strategy_name: str,
    filename: str = "monthly_heatmap.png",
) -> str:
    """绘制月度收益热力图"""
    _ensure_output()

    # 移除"全年"列用于热力图
    plot_data = monthly_returns.drop(columns=["全年"], errors="ignore") * 100

    fig, ax = plt.subplots(figsize=(14, max(4, len(plot_data) * 0.8)))
    sns.heatmap(
        plot_data, annot=True, fmt=".1f", center=0,
        cmap="RdYlGn", linewidths=0.5, ax=ax,
        cbar_kws={"label": "月收益率(%)"},
    )
    ax.set_title(f"月度收益热力图: {strategy_name}", fontsize=14)
    ax.set_xlabel("月份")
    ax.set_ylabel("年份")

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[图表] 月度热力图已保存: {path}")
    return path


def plot_parameter_sensitivity(
    param_results: pd.DataFrame,
    x_col: str,
    y_col: str = "夏普比率",
    strategy_name: str = "",
    filename: str = "param_sensitivity.png",
) -> str:
    """绘制参数敏感性图"""
    _ensure_output()

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    metrics = ["夏普比率", "年化收益率", "最大回撤"]
    colors = ["#1f77b4", "#2ca02c", "#d62728"]

    for ax, metric, color in zip(axes, metrics, colors):
        if metric in param_results.columns and x_col in param_results.columns:
            ax.plot(param_results[x_col], param_results[metric],
                    marker="o", color=color, linewidth=2)
            ax.set_title(f"{metric} vs {x_col}", fontsize=12)
            ax.set_xlabel(x_col)
            ax.set_ylabel(metric)
            ax.grid(True, alpha=0.3)

    fig.suptitle(f"参数敏感性分析: {strategy_name}", fontsize=14, y=1.02)
    fig.tight_layout()

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[图表] 参数敏感性已保存: {path}")
    return path


def plot_phase1_overview(
    results_df: pd.DataFrame,
    filename: str = "phase1_overview.png",
) -> str:
    """绘制阶段一所有指标的夏普比率 vs 最大回撤散点图"""
    _ensure_output()

    fig, ax = plt.subplots(figsize=(14, 10))
    colors = results_df["夏普比率"].values
    scatter = ax.scatter(
        results_df["最大回撤"], results_df["夏普比率"],
        c=colors, cmap="RdYlGn", s=80, edgecolors="black", linewidth=0.5,
    )
    plt.colorbar(scatter, ax=ax, label="夏普比率")

    # 标注策略名称
    for _, row in results_df.iterrows():
        ax.annotate(row["指标名称"], (row["最大回撤"], row["夏普比率"]),
                    fontsize=7, ha="center", va="bottom", alpha=0.8)

    ax.set_title("阶段一：全部指标 — 夏普比率 vs 最大回撤", fontsize=14)
    ax.set_xlabel("最大回撤 (%)")
    ax.set_ylabel("夏普比率")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=1.0, color="red", linestyle="--", alpha=0.5, label="夏普=1.0")
    ax.axvline(x=30, color="blue", linestyle="--", alpha=0.5, label="回撤=30%")
    ax.legend()

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[图表] Phase1概览已保存: {path}")
    return path
