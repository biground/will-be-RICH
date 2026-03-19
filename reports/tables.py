"""
报告表格生成模块
"""

import os
import pandas as pd
from tabulate import tabulate
from config import OUTPUT_DIR


def _ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_phase1_report(results: list[dict], top_n: int = 10) -> pd.DataFrame:
    """
    生成阶段一：单一指标测试报告。
    按夏普比率降序排列，标注TOP N。
    """
    _ensure_output()
    df = pd.DataFrame(results)
    df = df.sort_values("夏普比率", ascending=False).reset_index(drop=True)
    df.index += 1
    df["排名"] = range(1, len(df) + 1)
    df["TOP10"] = df["排名"].apply(lambda x: "★" if x <= top_n else "")

    # 选择输出列
    cols = ["排名", "TOP10", "指标名称", "年化收益率", "最大回撤", "夏普比率",
            "卡玛比率", "胜率", "盈亏比", "交易次数", "年化波动率"]
    output = df[cols]

    # 打印表格
    print("\n" + "=" * 100)
    print("阶段一：单一指标测试报告（按夏普比率降序）")
    print("=" * 100)
    print(tabulate(output, headers="keys", tablefmt="grid", showindex=False,
                   numalign="right", stralign="center"))

    # 保存CSV
    csv_path = os.path.join(OUTPUT_DIR, "phase1_single_indicators.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n已保存至 {csv_path}")

    return df


def generate_phase2_report(results: list[dict]) -> pd.DataFrame:
    """
    生成阶段二：组合指标测试报告。
    筛选条件: 夏普>1 且 回撤<30%。
    """
    _ensure_output()
    df = pd.DataFrame(results)
    if df.empty:
        print("\n阶段二：无满足条件的组合策略")
        return df

    df = df.sort_values("夏普比率", ascending=False).reset_index(drop=True)
    df["排名"] = range(1, len(df) + 1)

    cols = ["排名", "指标组合", "逻辑", "年化收益率", "最大回撤", "夏普比率",
            "卡玛比率", "胜率", "盈亏比", "交易次数"]
    output = df[[c for c in cols if c in df.columns]]

    print("\n" + "=" * 100)
    print("阶段二：组合指标测试报告（筛选后，按夏普比率降序）")
    print("=" * 100)
    print(tabulate(output, headers="keys", tablefmt="grid", showindex=False,
                   numalign="right", stralign="center"))

    csv_path = os.path.join(OUTPUT_DIR, "phase2_combinations.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n已保存至 {csv_path}")

    return df


def generate_best_strategy_report(
    core_metrics: dict,
    aux_metrics: dict,
    benchmark_metrics: dict,
    monthly_returns: pd.DataFrame,
    trade_log: pd.DataFrame,
) -> None:
    """生成最优策略详细报告"""
    _ensure_output()

    print("\n" + "=" * 100)
    print(f"最优策略详细报告: {core_metrics['指标名称']}")
    print("=" * 100)

    # 1. 核心结论
    print("\n【核心结论】")
    sharpe = core_metrics["夏普比率"]
    ann_ret = core_metrics["年化收益率"]
    max_dd = core_metrics["最大回撤"]
    win_rate = core_metrics["胜率"]
    bench_ret = benchmark_metrics["基准年化收益率"]
    excess = ann_ret - bench_ret

    print(f"  1. 策略年化收益率 {ann_ret}%，超越基准 {excess:.2f} 个百分点")
    print(f"  2. 夏普比率 {sharpe}，最大回撤 {max_dd}%，风险收益比优秀")
    print(f"  3. 胜率 {win_rate}%，交易 {core_metrics['交易次数']} 次，信号稳定")

    # 2. 完整指标表
    print("\n【核心指标】")
    for k, v in core_metrics.items():
        if k != "指标名称":
            unit = "%" if any(u in k for u in ["收益率", "回撤", "波动率", "胜率"]) else ""
            print(f"  {k}: {v}{unit}")

    print("\n【辅助指标】")
    for k, v in aux_metrics.items():
        unit = "%" if "VaR" in k or "CVaR" in k else ""
        print(f"  {k}: {v}{unit}")

    print("\n【基准对比】")
    for k, v in benchmark_metrics.items():
        unit = "%" if any(u in k for u in ["收益率", "回撤", "波动率"]) else ""
        print(f"  {k}: {v}{unit}")

    # 3. 月度收益表
    if monthly_returns is not None and not monthly_returns.empty:
        print("\n【月度收益率 (%)】")
        display_monthly = (monthly_returns * 100).round(2)
        print(tabulate(display_monthly, headers="keys", tablefmt="grid",
                       numalign="right", showindex=True))
        monthly_path = os.path.join(OUTPUT_DIR, "best_monthly_returns.csv")
        display_monthly.to_csv(monthly_path, encoding="utf-8-sig")

    # 4. 交易记录
    if trade_log is not None and not trade_log.empty:
        print(f"\n【交易记录】(共 {len(trade_log)} 笔)")
        print(tabulate(trade_log.head(30), headers="keys", tablefmt="grid",
                       showindex=False, numalign="right"))
        trade_path = os.path.join(OUTPUT_DIR, "best_trade_log.csv")
        trade_log.to_csv(trade_path, index=False, encoding="utf-8-sig")
        if len(trade_log) > 30:
            print(f"  ... 更多交易记录请查看 {trade_path}")


def generate_param_sensitivity_report(param_results: pd.DataFrame, strategy_name: str) -> None:
    """生成参数敏感性报告"""
    _ensure_output()

    print("\n" + "=" * 100)
    print(f"参数敏感性分析: {strategy_name}")
    print("=" * 100)

    if param_results.empty:
        print("  无参数变化数据")
        return

    print(tabulate(param_results, headers="keys", tablefmt="grid",
                   showindex=False, numalign="right"))

    csv_path = os.path.join(OUTPUT_DIR, "phase3_param_sensitivity.csv")
    param_results.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n已保存至 {csv_path}")


def generate_final_recommendation(top_strategies: list[dict]) -> None:
    """生成最终策略推荐"""
    print("\n" + "=" * 100)
    print("最终策略推荐（按综合评分排序）")
    print("=" * 100)

    for i, strat in enumerate(top_strategies, 1):
        print(f"\n{'─' * 80}")
        print(f"推荐 #{i}: {strat['name']}")
        print(f"{'─' * 80}")
        print(f"  策略描述: {strat.get('description', 'N/A')}")
        print(f"  核心参数: {strat.get('params', 'N/A')}")
        print(f"  年化收益: {strat.get('annual_return', 'N/A')}%")
        print(f"  夏普比率: {strat.get('sharpe', 'N/A')}")
        print(f"  最大回撤: {strat.get('max_dd', 'N/A')}%")
        print(f"  胜    率: {strat.get('win_rate', 'N/A')}%")
        print(f"  交易次数: {strat.get('trades', 'N/A')}")
        if strat.get('param_range'):
            print(f"  预期表现: 夏普 {strat['param_range']}")
        print(f"  适用场景: {strat.get('scenario', '趋势型市场')}")
        print(f"  风险提示: {strat.get('risk', '过去表现不代表未来收益')}")
        print(f"  改进建议: {strat.get('improvement', '可结合止损机制优化')}")

    print(f"\n{'=' * 100}")
    print("注意：以上策略基于历史数据回测，仅供研究参考，不构成投资建议。")
    print(f"{'=' * 100}")
