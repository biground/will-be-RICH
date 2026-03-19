"""
查看结果页面 — 浏览单次回测的详细结果
"""

import sys
import os
import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import storage

st.set_page_config(page_title="查看结果", page_icon="📊", layout="wide")
st.header("📊 查看结果")

# 获取所有运行记录
runs_df = storage.list_runs()

if runs_df.empty:
    st.info("暂无回测记录。请先运行一次回测。")
    st.page_link("pages/1_新建回测.py", label="去新建回测 →", icon="🚀")
    st.stop()

# 选择运行
run_options = {
    row["id"]: f"#{row['id']} | {row['etf_symbol']} ({row.get('etf_name', '')}) | {row['start_date']}~{row['end_date']} | {row['status']} | {row['run_time'][:16]}"
    for _, row in runs_df.iterrows()
}

selected_id = st.selectbox(
    "选择回测记录", list(run_options.keys()),
    format_func=lambda x: run_options[x],
    help="格式：# 编号 | ETF代码（名称） | 回测时间段 | 状态 | 运行时间。选择后页面展示该次回测的详细结果。",
)

run_info = storage.get_run(selected_id)
if not run_info:
    st.error("记录不存在")
    st.stop()

# 运行概要
st.markdown("### 运行概要")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("ETF", f"{run_info['etf_symbol']}")
c2.metric("区间", f"{run_info['start_date']}~{run_info['end_date']}")
c3.metric("初始资金", f"¥{run_info['init_cash']:,.0f}")
c4.metric("状态", run_info['status'])
c5.metric("耗时", f"{run_info.get('elapsed_seconds', 0) or 0:.1f}s")

if run_info.get("notes"):
    st.caption(f"备注: {run_info['notes']}")

st.markdown("---")

# 标签页
tab1, tab2, tab3, tab4 = st.tabs(["📈 阶段一: 单指标", "🔀 阶段二: 组合", "🔧 阶段三: 参数优化", "⭐ 最优策略"])

# ---- 阶段一 ----
with tab1:
    p1 = storage.get_phase1(selected_id)
    if p1.empty:
        st.info("无阶段一数据")
    else:
        st.subheader(f"单指标测试 ({len(p1)} 个策略)")

        # 散点图
        fig = px.scatter(
            p1, x="max_drawdown", y="sharpe",
            text="indicator_name",
            color="sharpe", color_continuous_scale="RdYlGn",
            hover_data=["annual_return", "win_rate", "trade_count"],
            labels={"max_drawdown": "最大回撤 (%)", "sharpe": "夏普比率",
                    "annual_return": "年化收益率 (%)", "win_rate": "胜率 (%)",
                    "trade_count": "交易次数", "indicator_name": "指标"},
            title="单指标: 夏普比率 vs 最大回撤",
        )
        fig.update_traces(textposition="top center", textfont_size=7)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        # 柱状图 TOP 10
        top10 = p1.head(10)
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=top10["indicator_name"], y=top10["sharpe"],
            name="夏普比率", marker_color="#1f77b4",
        ))
        fig_bar.add_trace(go.Bar(
            x=top10["indicator_name"], y=top10["annual_return"],
            name="年化收益率 (%)", marker_color="#2ca02c",
        ))
        fig_bar.update_layout(title="TOP 10 指标", barmode="group", height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

        # 表格
        display_df = p1.rename(columns={
            "indicator_name": "指标名称", "annual_return": "年化收益率",
            "max_drawdown": "最大回撤", "sharpe": "夏普比率",
            "win_rate": "胜率", "profit_loss_ratio": "盈亏比",
            "trade_count": "交易次数", "annual_vol": "年化波动率",
            "calmar": "卡玛比率", "sortino": "索提诺比率",
            "avg_hold_days": "平均持仓天数",
        })
        show_cols = ["指标名称", "年化收益率", "最大回撤", "夏普比率",
                     "胜率", "盈亏比", "交易次数", "年化波动率", "卡玛比率"]
        avail = [c for c in show_cols if c in display_df.columns]
        st.dataframe(display_df[avail], use_container_width=True, hide_index=True)

        # 下载
        csv = p1.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载阶段一数据 (CSV)", csv,
                           f"phase1_run{selected_id}.csv", "text/csv")

# ---- 阶段二 ----
with tab2:
    p2 = storage.get_phase2(selected_id)
    if p2.empty:
        st.info("无阶段二数据")
    else:
        st.subheader(f"组合策略测试 ({len(p2)} 个组合)")

        # 按逻辑分组对比
        fig = px.scatter(
            p2, x="max_drawdown", y="sharpe",
            color="logic", text="combo_name",
            hover_data=["annual_return", "win_rate", "trade_count"],
            labels={"max_drawdown": "最大回撤 (%)", "sharpe": "夏普比率",
                    "combo_name": "组合", "logic": "逻辑",
                    "annual_return": "年化收益率 (%)", "win_rate": "胜率 (%)"},
            title="组合策略: 夏普比率 vs 最大回撤",
        )
        fig.update_traces(textposition="top center", textfont_size=7)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        display_df = p2.rename(columns={
            "combo_name": "组合名称", "logic": "逻辑",
            "annual_return": "年化收益率", "max_drawdown": "最大回撤",
            "sharpe": "夏普比率", "win_rate": "胜率",
            "profit_loss_ratio": "盈亏比", "trade_count": "交易次数",
        })
        show_cols = ["组合名称", "逻辑", "年化收益率", "最大回撤", "夏普比率",
                     "胜率", "盈亏比", "交易次数"]
        avail = [c for c in show_cols if c in display_df.columns]
        st.dataframe(display_df[avail].head(30), use_container_width=True, hide_index=True)

        csv = p2.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载阶段二数据 (CSV)", csv,
                           f"phase2_run{selected_id}.csv", "text/csv")

# ---- 阶段三 ----
with tab3:
    p3 = storage.get_phase3(selected_id)
    if p3.empty:
        st.info("无阶段三数据")
    else:
        st.subheader(f"参数优化结果 ({len(p3)} 组参数组合)")
        st.info(
            "**阶段三做了什么？** 系统对最优策略的核心参数（如均线周期、RSI阈值等）进行±20%范围的网格扫描，"
            "测试每组参数下的策略表现，帮助你判断：①当前参数是否处于'甜蜜区'（改变参数后表现稳定）；"
            "②还有没有更好的参数组合。\n\n"
            "**怎么操作？** 选择一个参数（X轴）和评价指标（Y轴），观察散点图的趋势："
            "若曲线平滑无突兀峰谷，说明策略对参数变化不敏感、稳定性好；若变化剧烈，说明参数选择很关键。"
        )

        # 解析参数 JSON
        params_expanded = []
        for _, row in p3.iterrows():
            d = dict(row)
            try:
                pj = json.loads(d.get("param_json", "{}"))
                d.update(pj)
            except Exception:
                pass
            params_expanded.append(d)
        p3_exp = pd.DataFrame(params_expanded)

        # 找参数列
        skip_cols = {"id", "run_id", "strategy_name", "param_json",
                     "total_return", "annual_return", "max_drawdown",
                     "sharpe", "win_rate", "trade_count"}
        param_cols = [c for c in p3_exp.columns if c not in skip_cols]

        if param_cols:
            x_col = st.selectbox(
                "X轴参数", param_cols,
                help="选择要分析的策略参数，如快速周期、慢速周期等，建议优先选业务含义最强的参数。",
            )
            y_metric = st.selectbox(
                "Y轴指标", ["sharpe", "annual_return", "max_drawdown"],
                format_func=lambda x: {"sharpe": "夏普比率", "annual_return": "年化收益率", "max_drawdown": "最大回撤"}[x],
                help="建议首选《夏普比率》——它同时考虑收益和风险，是评价策略综合质量的核心指标。",
            )
            label_map = {"sharpe": "夏普比率", "annual_return": "年化收益率 (%)", "max_drawdown": "最大回撤 (%)"}
            fig = px.scatter(
                p3_exp, x=x_col, y=y_metric,
                color="annual_return",
                color_continuous_scale="RdYlGn",
                title=f"参数敏感性: {x_col} vs {label_map.get(y_metric, y_metric)}",
                hover_data=["sharpe", "annual_return", "max_drawdown"],
            )
            fig.update_layout(height=450)
            st.caption("每个点代表一组参数配置：横轴是你选择的参数值，纵轴是该参数下的策略表现。颜色越绿表示年化收益越高。")
            st.plotly_chart(fig, use_container_width=True)

        # 结果表格（带列名翻译）
        p3_display = p3_exp.drop(columns=["param_json", "id", "run_id"], errors="ignore")
        col_rename = {
            "strategy_name": "策略名称",
            "total_return": "总收益率(%)",
            "annual_return": "年化收益率(%)",
            "max_drawdown": "最大回撤(%)",
            "sharpe": "夏普比率",
            "win_rate": "胜率(%)",
            "trade_count": "交易次数",
        }
        p3_display = p3_display.rename(columns=col_rename)
        st.caption("下表按夏普比率从高到低排序，每行代表一组参数配置的完整回测结果。参数列（如 fast/slow）即被扫描的策略参数值。")
        st.dataframe(p3_display.head(50), use_container_width=True, hide_index=True)

# ---- 最优策略 ----
with tab4:
    best = storage.get_best_strategy(selected_id)
    if not best:
        st.info("无最优策略数据")
    else:
        st.subheader(f"⭐ 最优策略: {best['strategy_name']}")

        core = best.get("core_metrics", {})
        aux = best.get("aux_metrics", {})
        bench = best.get("benchmark_metrics", {})

        # 指标说明区
        with st.expander("📖 如何理解这些指标？"):
            st.markdown("""
| 指标 | 含义 | 评判参考 |
|------|------|------|
| **年化收益率** | 将回测期间总收益折算为年均百分比 | 超过基准越好 |
| **夏普比率** | 每单位风险的超额收益，越高越好 | >1良好，>2优秀 |
| **最大回撤** | 从山顶到谷底的最大跌幅，表示最坏亏损场景 | 越小越好 |
| **胜率** | 盈利交易次数 / 总交易次数 | 高胜率不代表盈利，需配合盈亏比看 |
| **盈亏比** | 平均盈利交易额 / 平均亏损交易额 | >1 表示赚多亏少 |
| **盈利因子** | 所有盈利交易收益之和 / 所有亏损交易损失之和 | >1.5 较好 |
| **索提诺比率** | 类似夏普，但只计下行波动风险，对亏损更敏感 | 越高越好 |
| **卡玛比率** | 年化收益 / 最大回撤，衡量每单位回撤的回报 | >0.5 可接受 |
| **VaR 95%** | 95% 置信度下单日最大预期亏损额 | 越小越好 |
| **CVaR 95%** | 超过 VaR 的极端情形平均亏损（尾部风险） | 越小越好 |
| **年化波动率** | 收益率的年化标准差，反映策略波动幅度 | 越低越平稳 |
            """)

        # 核心指标
        st.markdown("#### 核心指标")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("年化收益率", f"{core.get('年化收益率', 0):.2f}%",
                   delta=f"超基准 {core.get('年化收益率', 0) - bench.get('基准年化收益率', 0):.2f}%")
        c2.metric("夏普比率", f"{core.get('夏普比率', 0):.3f}")
        c3.metric("最大回撤", f"{core.get('最大回撤', 0):.2f}%")
        c4.metric("胜率", f"{core.get('胜率', 0):.1f}%")
        c5.metric("交易次数", f"{core.get('交易次数', 0)}")
        c6.metric("盈亏比", f"{core.get('盈亏比', 0):.3f}")

        # 辅助指标
        st.markdown("#### 辅助指标")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("盈利因子", f"{aux.get('盈利因子', 0):.3f}")
        c2.metric("索提诺比率", f"{core.get('索提诺比率', 0):.3f}")
        c3.metric("卡玛比率", f"{core.get('卡玛比率', 0):.3f}")
        c4.metric("VaR 95%", f"{aux.get('VaR_95', 0):.3f}%")
        c5.metric("CVaR 95%", f"{aux.get('CVaR_95', 0):.3f}%")
        c6.metric("预期收益", f"¥{aux.get('预期收益', 0):,.2f}")

        # 基准对比
        st.markdown("#### 基准对比")
        st.caption("💡 **基准**是指在回测期间内、对目标指数实行“买入并持有不动”的策略表现。若策略年化收益低于基准，说明直接定期买入并持有优于该策略。")
        comp_data = {
            "指标": ["年化收益率", "最大回撤", "年化波动率", "夏普比率"],
            "策略": [
                core.get("年化收益率", 0),
                core.get("最大回撤", 0),
                core.get("年化波动率", 0),
                core.get("夏普比率", 0),
            ],
            "基准": [
                bench.get("基准年化收益率", 0),
                bench.get("基准最大回撤", 0),
                bench.get("基准年化波动率", 0),
                bench.get("基准夏普比率", 0),
            ],
        }
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=comp_data["指标"], y=comp_data["策略"],
                                   name="策略", marker_color="#1f77b4"))
        fig_comp.add_trace(go.Bar(x=comp_data["指标"], y=comp_data["基准"],
                                   name="基准", marker_color="#ff7f0e"))
        fig_comp.update_layout(barmode="group", title="策略 vs 基准", height=350)
        st.plotly_chart(fig_comp, use_container_width=True)

        # 月度收益
        monthly_json = best.get("monthly_returns_json", "{}")
        if monthly_json and monthly_json != "{}":
            try:
                monthly_df = pd.read_json(monthly_json)
                if not monthly_df.empty:
                    st.markdown("#### 月度收益热力图")
                    st.caption("🟢 绿色 = 当月盈利；🔴 红色 = 当月亏损；颜色越深表示收益/损失幅度越大。可快速判断策略在哪些年廞/月份表现较充裕。")
                    plot_data = monthly_df.drop(columns=["全年"], errors="ignore") * 100
                    fig = px.imshow(
                        plot_data, text_auto=".1f",
                        color_continuous_scale="RdYlGn",
                        color_continuous_midpoint=0,
                        labels=dict(x="月份", y="年份", color="收益率(%)"),
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

        # 交易记录
        trade_json = best.get("trade_log_json", "{}")
        if trade_json and trade_json != "{}":
            try:
                trade_df = pd.read_json(trade_json)
                if not trade_df.empty:
                    # 将毫秒时间戳转为可读日期
                    for _tcol in ["买入时间", "卖出时间"]:
                        if _tcol in trade_df.columns:
                            trade_df[_tcol] = pd.to_datetime(
                                trade_df[_tcol], unit="ms", errors="coerce"
                            ).dt.strftime("%Y-%m-%d")
                    st.markdown("#### 交易记录")
                    st.dataframe(trade_df, use_container_width=True, hide_index=True)
            except Exception:
                pass
