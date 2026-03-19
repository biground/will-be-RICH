"""
历史记录页面 — 管理与对比多次回测
"""

import sys
import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import storage

st.set_page_config(page_title="历史记录", page_icon="📚", layout="wide")
st.markdown("""
<style>
div[data-testid="stAppViewContainer"] > div:first-child { padding-top: 3.2rem; }
.fixed-nav {
    position: fixed; top: 0; left: 0; right: 0; z-index: 999;
    background: linear-gradient(135deg, #1f77b4 0%, #2196F3 100%);
    display: flex; justify-content: center; gap: 0; padding: 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.fixed-nav a {
    color: rgba(255,255,255,0.85); text-decoration: none;
    padding: 0.65rem 2rem; font-size: 0.95rem; font-weight: 500;
    transition: all 0.2s; border-bottom: 3px solid transparent;
}
.fixed-nav a:hover { color: #fff; background: rgba(255,255,255,0.1); }
.fixed-nav a.active { color: #fff; border-bottom: 3px solid #fff; background: rgba(255,255,255,0.15); }
</style>
<div class="fixed-nav">
    <a href="/" target="_self">🏠 首页</a>
    <a href="/新建回测" target="_self">🚀 新建回测</a>
    <a href="/查看结果" target="_self">📊 查看结果</a>
    <a href="/历史记录" target="_self" class="active">📚 历史记录</a>
</div>
""", unsafe_allow_html=True)
st.header("📚 历史记录与对比")

runs_df = storage.list_runs()

if runs_df.empty:
    st.info("暂无回测记录。")
    st.page_link("pages/1_新建回测.py", label="去新建回测 →", icon="🚀")
    st.stop()

# ============================================================
# 回测记录列表
# ============================================================
st.subheader("所有回测记录")

display_df = runs_df[[
    "id", "etf_symbol", "etf_name", "start_date", "end_date",
    "data_freq", "init_cash", "status", "elapsed_seconds", "run_time", "notes",
]].copy()
display_df.columns = [
    "ID", "ETF代码", "ETF名称", "起始日期", "结束日期",
    "频率", "初始资金", "状态", "耗时(s)", "运行时间", "备注",
]

st.dataframe(display_df, use_container_width=True, hide_index=True)

# 删除功能
st.markdown("---")
with st.expander("🗑️ 删除记录"):
    del_id = st.selectbox(
        "选择要删除的记录",
        runs_df["id"].tolist(),
        format_func=lambda x: f"#{x} - {runs_df[runs_df['id']==x].iloc[0]['etf_symbol']} ({runs_df[runs_df['id']==x].iloc[0]['run_time'][:16]})",
        help="⚠️ 删除操作**不可撤销**，将永久移除该次回测的所有参数、策略和结果数据。",
    )
    if st.button("确认删除", type="secondary"):
        storage.delete_run(del_id)
        st.success(f"已删除记录 #{del_id}")
        st.rerun()

# ============================================================
# 跨回测对比
# ============================================================
st.markdown("---")
st.subheader("策略对比")

completed_runs = runs_df[runs_df["status"] == "completed"]
if len(completed_runs) < 1:
    st.info("需要至少1条已完成的回测记录来进行对比。")
    st.stop()

# 选择要对比的记录
compare_ids = st.multiselect(
    "选择要对比的回测 (可多选)",
    completed_runs["id"].tolist(),
    default=completed_runs["id"].tolist()[:3],
    format_func=lambda x: f"#{x} - {completed_runs[completed_runs['id']==x].iloc[0]['etf_symbol']} ({completed_runs[completed_runs['id']==x].iloc[0]['start_date']}~{completed_runs[completed_runs['id']==x].iloc[0]['end_date']})",
    help="多选不同标的或参数组合的回测，横向比较哪套策略在哪类市场环境下表现最优。建议选择同一ETF的不同参数组合，或不同ETF在同一时段的结果。",
)

if not compare_ids:
    st.stop()

# 收集各次回测的最优策略
compare_data = []
for rid in compare_ids:
    best = storage.get_best_strategy(rid)
    run = storage.get_run(rid)
    if best and run:
        core = best.get("core_metrics", {})
        bench = best.get("benchmark_metrics", {})
        compare_data.append({
            "回测ID": f"#{rid}",
            "ETF": f"{run['etf_symbol']} ({run.get('etf_name', '')})",
            "区间": f"{run['start_date']}~{run['end_date']}",
            "最优策略": best["strategy_name"],
            "年化收益率": core.get("年化收益率", 0),
            "夏普比率": core.get("夏普比率", 0),
            "最大回撤": core.get("最大回撤", 0),
            "胜率": core.get("胜率", 0),
            "交易次数": core.get("交易次数", 0),
            "盈亏比": core.get("盈亏比", 0),
            "基准年化": bench.get("基准年化收益率", 0),
            "基准回撤": bench.get("基准最大回撤", 0),
        })

if not compare_data:
    st.info("所选记录暂无最优策略数据。")
    st.stop()

comp_df = pd.DataFrame(compare_data)
st.dataframe(comp_df, use_container_width=True, hide_index=True)

# 对比图
if len(comp_df) >= 1:
    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["年化收益率"],
                              name="策略年化", marker_color="#1f77b4"))
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["基准年化"],
                              name="基准年化", marker_color="#ff7f0e"))
        fig.update_layout(title="年化收益率对比", barmode="group", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["夏普比率"],
                              name="夏普比率", marker_color="#2ca02c"))
        fig.update_layout(title="夏普比率对比", height=350)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["最大回撤"],
                              name="策略回撤", marker_color="#d62728"))
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["基准回撤"],
                              name="基准回撤", marker_color="#ff9896"))
        fig.update_layout(title="最大回撤对比", barmode="group", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=comp_df["回测ID"], y=comp_df["胜率"],
                              name="胜率 (%)", marker_color="#9467bd"))
        fig.update_layout(title="胜率对比", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 各ETF最优指标统计
# ============================================================
st.markdown("---")
st.subheader("指标频率统计")
st.caption("统计所有已完成回测中，阶段一排名前10的指标出现次数")

indicator_counts = {}
for rid in completed_runs["id"].tolist():
    p1 = storage.get_phase1(rid)
    if not p1.empty:
        top10 = p1.head(10)["indicator_name"].tolist()
        for name in top10:
            indicator_counts[name] = indicator_counts.get(name, 0) + 1

if indicator_counts:
    freq_df = pd.DataFrame([
        {"指标名称": k, "出现次数": v}
        for k, v in sorted(indicator_counts.items(), key=lambda x: -x[1])
    ])
    fig = px.bar(freq_df.head(20), x="指标名称", y="出现次数",
                  title="频繁出现的优秀指标 (TOP 20)",
                  color="出现次数", color_continuous_scale="Blues")
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(freq_df, use_container_width=True, hide_index=True)
else:
    st.info("暂无足够数据进行统计。")
