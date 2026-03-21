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
import ui_utils

st.set_page_config(page_title="历史记录", page_icon=None, layout="wide")
ui_utils.render_nav("history")
st.markdown(ui_utils.section_header("历史记录与对比"), unsafe_allow_html=True)

runs_df = storage.list_runs()

if runs_df.empty:
    st.info("暂无回测记录。")
    st.page_link("pages/1_新建回测.py", label="去新建回测 →", icon="🚀")
    st.stop()

# ============================================================
# 逐行展示回测记录（关注 | 删除 | 详情）
# ============================================================
st.markdown(ui_utils.section_header("所有回测记录"), unsafe_allow_html=True)

for _, run_row in runs_df.iterrows():
    rid = run_row["id"]
    etf_sym = run_row["etf_symbol"]
    etf_nm = run_row.get("etf_name", etf_sym)
    status = run_row.get("status", "")
    run_time = str(run_row.get("run_time", ""))[:16]
    start_d = run_row.get("start_date", "")
    end_d = run_row.get("end_date", "")
    elapsed = run_row.get("elapsed_seconds")
    init_cash = run_row.get("init_cash")
    notes = run_row.get("notes", "") or ""

    best = storage.get_best_strategy(rid) if status == "completed" else None
    best_name = best["strategy_name"] if best else ""
    is_watched = storage.is_in_watchlist(etf_sym, strategy_name=best_name) if best_name else False

    # ---- 行布局：关注(1) | 删除(1) | 摘要(8) ----
    c_follow, c_delete, c_info = st.columns([1, 1, 8])

    with c_follow:
        if best_name:
            btn_label = "⭐ 已关注" if is_watched else "☆ 关注"
            btn_type = "secondary" if is_watched else "primary"
            if st.button(btn_label, key=f"follow_{rid}", type=btn_type, use_container_width=True):
                if is_watched:
                    storage.remove_from_watchlist(etf_sym, strategy_name=best_name)
                else:
                    storage.add_to_watchlist(etf_sym, etf_nm, strategy_name=best_name, run_id=rid)
                st.rerun()
        else:
            st.caption("无策略")

    with c_delete:
        if st.button("🗑️ 删除", key=f"del_{rid}", type="secondary", use_container_width=True):
            storage.delete_run(rid)
            st.toast(f"已删除记录 #{rid}")
            st.rerun()

    with c_info:
        status_icon = "✅" if status == "completed" else ("⏳" if status == "running" else "❌")
        title = f"**#{rid}** {etf_sym} {etf_nm} · {start_d}~{end_d} {status_icon}"
        with st.expander(title, expanded=False):
            # 运行概要
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("ETF", f"{etf_sym}")
            m2.metric("区间", f"{start_d}~{end_d}")
            m3.metric("初始资金", f"¥{init_cash:,.0f}" if init_cash else "—")
            m4.metric("状态", status)
            m5.metric("耗时", f"{elapsed:.1f}s" if elapsed else "—")

            if notes:
                st.caption(f"📝 {notes}")

            # 最优策略信息
            if best:
                st.markdown("---")
                core = best.get("core_metrics", {})
                bench = best.get("benchmark_metrics", {})
                st.markdown(f"**最优策略：** {best_name}")
                k1, k2, k3, k4, k5, k6 = st.columns(6)
                k1.metric("年化收益率", f"{core.get('年化收益率', 0):.1f}%")
                k2.metric("最大回撤", f"{abs(core.get('最大回撤', 0)):.1f}%")
                k3.metric("夏普比率", f"{core.get('夏普比率', 0):.2f}")
                k4.metric("胜率", f"{core.get('胜率', 0):.1f}%")
                k5.metric("交易次数", f"{core.get('交易次数', 0):.0f}")
                k6.metric("盈亏比", f"{core.get('盈亏比', 0):.2f}")

                if bench:
                    b1, b2 = st.columns(2)
                    b1.metric("基准年化", f"{bench.get('基准年化收益率', 0):.1f}%")
                    b2.metric("基准回撤", f"{abs(bench.get('基准最大回撤', 0)):.1f}%")

                # 跳转到策略报告
                if st.button("📊 查看完整报告", key=f"report_{rid}"):
                    st.session_state["_jump_run_id"] = rid
                    st.switch_page("pages/2_策略报告.py")
            else:
                if status == "completed":
                    st.caption("该回测暂未选定最优策略。")

    st.markdown("<hr style='margin:0.3rem 0;border:none;border-top:1px solid #E5E7EB;'>", unsafe_allow_html=True)

# ============================================================
# 跨回测对比
# ============================================================
st.markdown("---")
st.markdown(ui_utils.section_header("策略对比"), unsafe_allow_html=True)

completed_runs = runs_df[runs_df["status"] == "completed"]
if len(completed_runs) < 1:
    st.info("需要至少1条已完成的回测记录来进行对比。")
    st.stop()

compare_ids = st.multiselect(
    "选择要对比的回测 (可多选)",
    completed_runs["id"].tolist(),
    default=completed_runs["id"].tolist()[:3],
    format_func=lambda x: f"#{x} - {completed_runs[completed_runs['id']==x].iloc[0]['etf_symbol']} ({completed_runs[completed_runs['id']==x].iloc[0]['start_date']}~{completed_runs[completed_runs['id']==x].iloc[0]['end_date']})",
    help="多选不同标的或参数组合的回测，横向比较哪套策略在哪类市场环境下表现最优。",
)

if not compare_ids:
    st.stop()

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
st.markdown(ui_utils.section_header("指标频率统计", "统计所有已完成回测中阶段一排名前10的指标出现次数"), unsafe_allow_html=True)

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
