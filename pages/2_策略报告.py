"""
策略报告页面 — 浏览单次回测的详细结果
默认展示「简单报告」，面向普通用户；可展开「专业分析」查看完整数据。
"""

import sys
import os
import json
import re
import glob
import time

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import storage
import ui_utils
from metrics_translator import (
    translate_metrics,
    get_strategy_grade_summary,
    get_risk_warning,
    traffic_light_card_html,
    signal_card_html,
)
from signal_interpreter import get_current_signals, get_consensus_signal

st.set_page_config(page_title="策略报告", page_icon=None, layout="wide")
ui_utils.render_nav("results")
st.markdown(ui_utils.section_header("策略报告"), unsafe_allow_html=True)


# ============================================================
# 辅助函数：采用策略时运行单次回测并持久化到数据库
# ============================================================
def _adopt_and_save(run_id, strategy_name, source, logic="", params=None):
    """
    采用某策略为最佳策略：运行单次回测获取完整 portfolio，然后持久化到数据库。
    会自动缓存回测数据，支持 P1 单指标和 P2 组合策略。
    """
    import glob as _glob
    from engine.backtester import run_single_backtest, run_combination_backtest
    from engine.metrics import (
        calculate_core_metrics, calculate_aux_metrics,
        calculate_benchmark_metrics, get_monthly_returns, get_trade_log,
    )
    from indicators import get_all_indicators

    _run = storage.get_run(run_id)
    if not _run:
        st.error("回测记录不存在")
        return False

    etf_sym = _run.get("etf_symbol", "")
    bench_sym = _run.get("benchmark_symbol", "")
    _ep = _run.get("extra_params", {})
    init_cash = _run.get("init_cash", 100000)
    entry_fees = _run.get("entry_fees", 0.0012)
    exit_fees = _run.get("exit_fees", 0.0017)

    # 加载缓存数据
    cache_dir = os.path.join(ROOT, "data", "cache")
    etf_df = None
    bench_df = None
    if os.path.isdir(cache_dir):
        for _pat in [
            os.path.join(cache_dir, f"{etf_sym}_*_qfq.csv"),
            os.path.join(cache_dir, f"{etf_sym}_*_index.csv"),
        ]:
            for _cf in _glob.glob(_pat):
                try:
                    _tmp = pd.read_csv(_cf, index_col="date", parse_dates=True)
                    if len(_tmp) >= 60:
                        etf_df = _tmp
                        break
                except Exception:
                    pass
            if etf_df is not None:
                break
        # 加载基准
        for _pat in [
            os.path.join(cache_dir, f"{bench_sym}_*_index.csv"),
            os.path.join(cache_dir, f"{bench_sym}_*_qfq.csv"),
        ]:
            for _cf in _glob.glob(_pat):
                try:
                    _tmp = pd.read_csv(_cf, index_col="date", parse_dates=True)
                    if len(_tmp) >= 60:
                        bench_df = _tmp
                        break
                except Exception:
                    pass
            if bench_df is not None:
                break

    if etf_df is None or len(etf_df) < 60:
        st.error(f"⚠️ 找不到 {etf_sym} 的本地缓存数据，无法生成完整策略分析。")
        return False

    if bench_df is None:
        bench_df = etf_df.copy()

    close = etf_df["close"]
    bench_close = bench_df["close"]

    # 生成指标信号
    all_signals = get_all_indicators(etf_df)
    signal_map = {name: (entries, exits) for entries, exits, name in all_signals}

    pf = None
    display_name = strategy_name

    if source == "P2" and " + " in strategy_name:
        # 组合策略
        parts = strategy_name.split(" + ")
        n1, n2 = parts[0].strip(), parts[1].strip()
        if n1 in signal_map and n2 in signal_map:
            e1, x1 = signal_map[n1]
            e2, x2 = signal_map[n2]
            pf = run_combination_backtest(close, e1, x1, e2, x2, logic=logic or "AND",
                                          init_cash=init_cash)
            display_name = f"{strategy_name} [{logic}]" if logic else strategy_name
    else:
        # 单指标策略
        target = strategy_name.split(" + ")[0].strip() if " + " in strategy_name else strategy_name
        if target in signal_map:
            e, x = signal_map[target]
            pf = run_single_backtest(close, e, x, init_cash=init_cash,
                                     entry_fees=entry_fees, exit_fees=exit_fees)

    if pf is None:
        st.warning("无法找到该策略的信号数据，已保存基本信息。")
        return False

    core = calculate_core_metrics(pf, display_name)
    aux = calculate_aux_metrics(pf)
    bench_metrics = calculate_benchmark_metrics(bench_close)
    monthly = get_monthly_returns(pf)
    trade_log = get_trade_log(pf)
    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]

    # 持久化到数据库
    storage.save_best_strategy(
        run_id, display_name, core, aux, bench_metrics, monthly, trade_log, equity
    )

    # 同步到 session_state
    st.session_state["adopted_strategy"] = {
        "source": source,
        "strategy_name": display_name,
        "logic": logic,
        "params": params or {},
        "sharpe": float(core.get("夏普比率", 0)),
        "annual_return": float(core.get("年化收益率", 0)),
        "max_drawdown": float(core.get("最大回撤", 0)),
        "win_rate": float(core.get("胜率", 0)) if core.get("胜率") is not None else None,
        "trade_count": int(core.get("交易次数", 0)) if core.get("交易次数") is not None else None,
    }
    return True

# 获取所有运行记录
runs_df = storage.list_runs()

if runs_df.empty:
    st.info("暂无回测记录。请先运行一次回测。")
    st.page_link("pages/1_新建回测.py", label="去新建回测 →", icon="🚀")
    st.stop()

# 如果从回测页跳转过来，优先使用 current_run_id
_jump_run_id = st.session_state.get("current_run_id")

# 选择运行
run_options = {
    row["id"]: f"#{row['id']} | {row['etf_symbol']} ({row.get('etf_name', '')}) | {row['start_date']}~{row['end_date']} | {row['status']} | {row['run_time'][:16]}"
    for _, row in runs_df.iterrows()
}

# 确定默认选中的 run_id
_default_idx = 0
if _jump_run_id and _jump_run_id in run_options:
    _default_idx = list(run_options.keys()).index(_jump_run_id)

selected_id = st.selectbox(
    "选择回测记录", list(run_options.keys()),
    index=_default_idx,
    format_func=lambda x: run_options[x],
    help="格式：# 编号 | ETF代码（名称） | 回测时间段 | 状态 | 运行时间",
)

run_info = storage.get_run(selected_id)
if not run_info:
    st.error("记录不存在")
    st.stop()

st.markdown("---")

# ============================================================
# 标签页：阶段一 + 阶段二 + 阶段三 + 完整数据
# ============================================================
tab_p1, tab_p2, tab_p3, tab_pro = st.tabs([
    "📈 阶段一: 单指标", "🔀 阶段二: 组合",
    "🔧 阶段三: 参数优化", "⭐ 完整数据",
])

# ================================================================
# 阶段一：单指标（原专业视图）
# ================================================================
with tab_p1:
    p1 = storage.get_phase1(selected_id)
    if p1.empty:
        st.info("无阶段一数据")
    else:
        st.markdown(ui_utils.section_header(f"单指标测试 ({len(p1)} 个策略)"), unsafe_allow_html=True)

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

        csv = p1.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载阶段一数据 (CSV)", csv,
                           f"phase1_run{selected_id}.csv", "text/csv")

        # --- 采用阶段一策略 ---
        st.markdown("---")
        _p1_names = p1["indicator_name"].tolist()
        _p1_sel = st.selectbox("选择要采用的单指标策略", _p1_names, key="_p1_adopt_sel",
                               help="选择任意单指标策略作为最佳策略，将保存到数据库并显示完整分析")
        if st.button("✅ 采用此策略为最佳配置", key="_p1_adopt_btn"):
            with st.spinner("正在生成完整策略分析..."):
                if _adopt_and_save(selected_id, _p1_sel, "P1"):
                    st.success("✅ 已选定并保存！切换到「完整数据」标签查看详细分析。")
                    st.rerun()

# ================================================================
# 阶段二：组合
# ================================================================
with tab_p2:
    p2 = storage.get_phase2(selected_id)
    if p2.empty:
        st.info("无阶段二数据")
    else:
        st.markdown(ui_utils.section_header(f"组合策略测试 ({len(p2)} 个组合)"), unsafe_allow_html=True)

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

        # --- 采用阶段二策略 ---
        st.markdown("---")
        _p2_names = p2["combo_name"].tolist()
        _p2_sel = st.selectbox("选择要采用的策略", _p2_names, key="_p2_adopt_sel",
                               help="选择任意组合策略作为最佳策略，将保存到数据库并显示完整分析")
        if st.button("✅ 采用此策略为最佳配置", key="_p2_adopt_btn"):
            _row = p2[p2["combo_name"] == _p2_sel].iloc[0]
            _logic = _row.get("logic", "")
            with st.spinner("正在生成完整策略分析..."):
                if _adopt_and_save(selected_id, _p2_sel, "P2", logic=_logic):
                    st.success("✅ 已选定并保存！切换到「完整数据」标签查看详细分析。")
                    st.rerun()

# ================================================================
# 阶段三：参数优化
# ================================================================
with tab_p3:
    def _supports_p3(cand: str) -> bool:
        """检查候选策略名是否支持阶段三参数优化。"""
        _name = cand.replace(" [AND]", "").replace(" [OR]", "")
        _target = _name.split(" + ")[0].strip() if " + " in _name else _name
        _p3_patterns = [
            r"^MA\(\d+,\d+\)$",
            r"^EMA\(\d+,\d+\)$",
            r"^RSI\(\d+\)$",
            r"^MACD\(\d+,\d+,\d+\)$",
            r"^SuperTrend\(\d+,[\d.]+\)$",
            r"^SAR\([\d.]+,[\d.]+\)$",
            r"^Bollinger\(\d+,[\d.]+\)$",
        ]
        return any(re.match(p, _target) for p in _p3_patterns)

    p3 = storage.get_phase3(selected_id)

    st.markdown(ui_utils.section_header("阶段三: 参数优化"), unsafe_allow_html=True)
    st.info(
        "**阶段三做了什么？** 对阶段一/二中所有支持参数化的策略，分别在原始参数 ±20% 范围内进行网格扫描，"
        "帮助你判断：①当前参数是否处于「甜蜜区」；②是否存在更优参数组合。"
    )

    # ---- 构建可优化策略列表 ----
    _p1 = storage.get_phase1(selected_id)
    _p2 = storage.get_phase2(selected_id)
    _candidates = []
    if not _p1.empty:
        for _, r in _p1.head(15).iterrows():
            _candidates.append(r.get("indicator_name", ""))
    if not _p2.empty:
        for _, r in _p2.head(15).iterrows():
            cname = r.get("combo_name", r.get("indicator_name", ""))
            logic = r.get("logic", "")
            _candidates.append(f"{cname} [{logic}]" if logic else cname)
    _candidates = [c for c in _candidates if c and _supports_p3(c)]
    # 去重：按实际扫描目标（第一个子指标）去重，避免同一指标因不同组合重复扫描
    def _scan_target(cand: str) -> str:
        _n = cand.replace(" [AND]", "").replace(" [OR]", "")
        return _n.split(" + ")[0].strip() if " + " in _n else _n

    _seen_targets = {}  # scan_target -> first candidate name
    _deduped = []
    for _c in _candidates:
        _t = _scan_target(_c)
        if _t not in _seen_targets:
            _seen_targets[_t] = _c
            _deduped.append(_c)
    _candidates = _deduped

    if not _candidates:
        if _p1.empty and _p2.empty:
            st.info("暂无阶段一/二的结果数据，请先运行回测。")
        else:
            st.info(
                "阶段一/二中的策略均不支持参数优化。"
                "参数优化目前支持：**MA、EMA、RSI、MACD、SuperTrend、SAR、Bollinger**。"
                "ADX、KDJ、CCI 等指标无固定参数，暂不支持自动扫描。"
            )
    else:
        # 已完成的策略 vs 待优化的策略
        _done_strats = (
            set(p3["strategy_name"].unique().tolist())
            if not p3.empty and "strategy_name" in p3.columns else set()
        )
        _pending = [c for c in _candidates if c not in _done_strats]
        _total = len(_candidates)
        _done_n = len(_done_strats & set(_candidates))

        _btn_label = (
            f"⚡ 运行参数优化（{_total} 个策略）"
            if _done_n == 0
            else f"🔄 重新优化全部（{_total} 个策略，已完成 {_done_n} 个）"
        )
        if st.button(_btn_label, type="primary", key="_p3_run_all_btn"):
            _etf_sym = run_info.get("etf_symbol", "")
            cache_dir = os.path.join(ROOT, "data", "cache")
            _etf_df = None
            if os.path.isdir(cache_dir):
                for _pat in [
                    os.path.join(cache_dir, f"{_etf_sym}_*_qfq.csv"),
                    os.path.join(cache_dir, f"{_etf_sym}_*_index.csv"),
                ]:
                    for _cf in glob.glob(_pat):
                        try:
                            _etf_df = pd.read_csv(_cf, index_col="date", parse_dates=True)
                            if len(_etf_df) >= 60:
                                break
                            _etf_df = None
                        except Exception:
                            _etf_df = None

            if _etf_df is None or len(_etf_df) < 60:
                st.error(f"⚠️ 找不到 {_etf_sym} 的本地缓存数据，请先重新运行一次回测以生成缓存。")
            else:
                _close = _etf_df["close"]
                _prog = st.progress(0)
                _stat = st.empty()
                _ok_count = 0
                try:
                    from main import _scan_indicator_params
                    for _i, _cand in enumerate(_candidates):
                        _opt_target = _scan_target(_cand)
                        _stat.text(f"[{_i+1}/{_total}] 正在优化「{_opt_target}」...")
                        _prog.progress(int(_i / _total * 90))
                        try:
                            _pdf = _scan_indicator_params(_etf_df, _close, _opt_target)
                            if _pdf is not None and not _pdf.empty:
                                storage.save_phase3(selected_id, _opt_target, _pdf)
                                _ok_count += 1
                        except Exception as _e:
                            st.warning(f"「{_cand}」优化失败：{_e}")
                    _prog.progress(100)
                    _stat.text("参数优化全部完成！")
                    st.success(f"✅ 完成！共优化 **{_ok_count}/{_total}** 个策略。")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"参数优化失败：{e}")
                    import traceback
                    with st.expander("查看详细错误"):
                        st.code(traceback.format_exc())

    # ================================================================
    # 参数说明字典（渲染函数需引用）
    # ================================================================
    _param_explain = {
        "fast": "快线周期（较短均线，反应更灵敏）",
        "slow": "慢线周期（较长均线，趋势更稳定）",
        "period": "计算周期（窗口长度，越大越平滑）",
        "multiplier": "波动乘数（越大止损越宽，交易越少）",
        "buy_threshold": "买入阈值（低于此值触发买入）",
        "sell_threshold": "卖出阈值（高于此值触发卖出）",
        "signal": "信号平滑周期",
        "af": "加速因子（越大止损越紧）",
        "max_af": "最大加速因子",
        "std": "标准差倍数（布林带宽度）",
    }

    # ================================================================
    # 展示优化结果（有数据时）
    # ================================================================
    if not p3.empty:
        st.markdown("---")

        p3_strat_list = (
            [s for s in p3["strategy_name"].unique().tolist() if s]
            if "strategy_name" in p3.columns else []
        )

        # ---- 共享评价指标（两列共用）----
        _label_map = {
            "sharpe": "夏普比率",
            "annual_return": "年化收益率 (%)",
            "max_drawdown": "最大回撤 (%)",
        }
        _ym_col, _ = st.columns([3, 5])
        with _ym_col:
            y_metric = st.selectbox(
                "评价指标（两侧同步）" if len(p3_strat_list) >= 2 else "评价指标",
                ["sharpe", "annual_return", "max_drawdown"],
                format_func=lambda x: _label_map[x],
                help="选择衡量参数组合表现的指标，推荐首选「夏普比率」",
                key="_p3_y_metric",
            )
        y_label = _label_map[y_metric]
        _colorscale = "RdYlGn_r" if y_metric == "max_drawdown" else "RdYlGn"

        # ================================================================
        # 渲染单侧结果（key_sfx 避免 widget key 冲突）
        # ================================================================
        def _render_p3_side(strat_name: str, key_sfx: str):
            _p3_cur = (
                p3[p3["strategy_name"] == strat_name].copy()
                if strat_name else p3.copy()
            )
            _pex = []
            for _, _row in _p3_cur.iterrows():
                _d = dict(_row)
                try:
                    _d.update(json.loads(_d.get("param_json", "{}")))
                except Exception:
                    pass
                _pex.append(_d)
            _df = pd.DataFrame(_pex).drop_duplicates()

            _skip = {"id", "run_id", "strategy_name", "param_json",
                     "total_return", "annual_return", "max_drawdown",
                     "sharpe", "win_rate", "trade_count"}
            _pcols = [c for c in _df.columns if c not in _skip]

            if _pcols:
                _desc = "、".join(
                    f"**{c}**（{_param_explain.get(c, c)}）" for c in _pcols
                )
                st.caption(f"扫描参数：{_desc}，共 **{len(_df)}** 组")

            if len(_pcols) == 2:
                _xc, _yc = _pcols[0], _pcols[1]
                try:
                    _piv = _df.pivot_table(
                        index=_yc, columns=_xc, values=y_metric, aggfunc="mean"
                    )
                    _fh = go.Figure(go.Heatmap(
                        z=_piv.values,
                        x=[str(v) for v in _piv.columns],
                        y=[str(v) for v in _piv.index],
                        colorscale=_colorscale,
                        text=[[f"{v:.3f}" if v is not None else ""
                               for v in _r] for _r in _piv.values],
                        texttemplate="%{text}",
                        hovertemplate=(
                            f"{_xc}: %{{x}}<br>{_yc}: %{{y}}"
                            f"<br>{y_label}: %{{z:.3f}}<extra></extra>"
                        ),
                        colorbar=dict(title=y_label),
                    ))
                    _fh.update_layout(
                        xaxis_title=_xc, yaxis_title=_yc,
                        height=400, margin=dict(l=50, r=10, t=40, b=50),
                        title=dict(text=f"热力图：{_xc} × {_yc}", font=dict(size=13)),
                    )
                    st.plotly_chart(_fh, use_container_width=True, key=f"_p3_heat_{key_sfx}")
                except Exception:
                    st.warning("热力图生成失败")

                _fl = px.line(
                    _df.sort_values(_xc), x=_xc, y=y_metric,
                    color=_yc,
                    color_discrete_sequence=px.colors.sequential.Viridis,
                    markers=True,
                    labels={y_metric: y_label, _xc: _xc, _yc: _yc},
                    title=f"折线图：{_xc}（按 {_yc} 分组）",
                )
                _fl.update_layout(height=360, margin=dict(t=40, b=40, l=50, r=10))
                st.plotly_chart(_fl, use_container_width=True, key=f"_p3_line2_{key_sfx}")

            elif len(_pcols) == 1:
                _xc = _pcols[0]
                _fl = px.line(
                    _df.sort_values(_xc), x=_xc, y=y_metric,
                    markers=True,
                    labels={y_metric: y_label},
                    title=f"参数敏感性：{_xc} → {y_label}",
                )
                _fl.update_layout(height=400, margin=dict(t=40, b=40, l=50, r=10))
                st.plotly_chart(_fl, use_container_width=True, key=f"_p3_line1_{key_sfx}")

            elif len(_pcols) > 2:
                _xc = st.selectbox("X 轴参数", _pcols, key=f"_p3_xcol_{key_sfx}")
                _cc_opts = [c for c in _pcols if c != _xc]
                _cc = (
                    st.selectbox("颜色区分", ["(无)"] + _cc_opts,
                                 key=f"_p3_color_{key_sfx}")
                    if _cc_opts else "(无)"
                )
                _fsc = px.scatter(
                    _df, x=_xc, y=y_metric,
                    color=(_cc if _cc != "(无)" else None),
                    color_continuous_scale=_colorscale,
                    hover_data=_pcols + ["sharpe", "annual_return", "max_drawdown"],
                    labels={y_metric: y_label},
                    title=f"散点图：{_xc} vs {y_label}",
                )
                _fsc.update_layout(height=400, margin=dict(t=40, b=40, l=50, r=10))
                st.plotly_chart(_fsc, use_container_width=True, key=f"_p3_scatter_{key_sfx}")

            # 最优参数推荐
            if not _df.empty and y_metric in _df.columns:
                _bidx = (
                    _df[y_metric].idxmin()
                    if y_metric == "max_drawdown"
                    else _df[y_metric].idxmax()
                )
                _br = _df.loc[_bidx]
                _bvals = {c: _br[c] for c in _pcols if c in _br}
                _vstr = "、".join(f"{k}={v}" for k, v in _bvals.items())
                _mval = _br[y_metric]
                st.success(f"🏆 最优参数：{_vstr}，{y_label} = **{_mval:.3f}**")
                if st.button("✅ 采用此参数配置", key=f"_p3_adopt_{key_sfx}",
                             help="将该最优参数组合保存到数据库，并在「完整数据」标签页查看详细分析"):
                    with st.spinner("正在生成完整策略分析..."):
                        if _adopt_and_save(selected_id, strat_name, "P3", params=_bvals):
                            st.success("✅ 已选定并保存！切换到「完整数据」标签查看详细分析。")
                            st.rerun()

            # 数据表（可折叠）
            with st.expander(f"全部 {len(_df)} 组数据", expanded=False):
                _disp = _df.drop(
                    columns=["param_json", "id", "run_id", "strategy_name"],
                    errors="ignore",
                )
                _disp = _disp.rename(columns={
                    "total_return": "总收益率(%)", "annual_return": "年化收益率(%)",
                    "max_drawdown": "最大回撤(%)", "sharpe": "夏普比率",
                    "win_rate": "胜率(%)", "trade_count": "交易次数",
                })
                _sc = "夏普比率" if "夏普比率" in _disp.columns else _disp.columns[0]
                st.dataframe(
                    _disp.sort_values(
                        _sc, ascending=(y_metric == "max_drawdown")
                    ).head(60),
                    use_container_width=True, hide_index=True,
                )
                _csv = _disp.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 下载 CSV", _csv,
                    f"phase3_{strat_name.replace(' ', '_')}.csv",
                    "text/csv",
                    key=f"_p3_dl_{key_sfx}",
                )

        # ================================================================
        # 布局：≥2 个策略 → 两栏对比；仅 1 个策略 → 单列
        # ================================================================
        if len(p3_strat_list) >= 2:
            # 两栏对比：每列各有独立选择器，默认分别选第 1、第 2 个策略
            _hl, _hr = st.columns(2)
            with _hl:
                _left_strat = st.selectbox(
                    "左侧策略",
                    p3_strat_list,
                    index=0,
                    key="_p3_left_sel",
                )
            with _hr:
                _right_default = 1 if len(p3_strat_list) > 1 else 0
                _right_strat = st.selectbox(
                    "右侧策略",
                    p3_strat_list,
                    index=_right_default,
                    key="_p3_right_sel",
                )

            _cl, _cr = st.columns(2)
            with _cl:
                _render_p3_side(_left_strat, "left")
            with _cr:
                _render_p3_side(_right_strat, "right")

        else:
            _render_p3_side(p3_strat_list[0] if p3_strat_list else "", "single")

# ================================================================
# 完整数据（原「最优策略」标签内容）
# ================================================================
with tab_pro:
    from engine.metrics import calculate_strategy_grade, get_rolling_sharpe, get_streak_stats

    best = storage.get_best_strategy(selected_id)
    if not best:
        st.info("请先在阶段一/二/三标签页中选择并采用一个策略，然后回到此处查看完整分析。")
    else:
        st.markdown(ui_utils.section_header(f"最优策略: {best['strategy_name']}"), unsafe_allow_html=True)

        core = best.get("core_metrics", {})
        aux = best.get("aux_metrics", {})
        bench = best.get("benchmark_metrics", {})

        # 策略综合评级
        grade_info = calculate_strategy_grade(core, aux)
        grade_colors = {"A": "#2e7d32", "B": "#1565c0", "C": "#f57f17", "D": "#e65100", "F": "#b71c1c"}
        gc = grade_colors.get(grade_info["grade"], "#666")
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:1.5rem;margin-bottom:1rem;">'
            f'<span style="font-size:3.5rem;font-weight:bold;color:{gc};'
            f'border:4px solid {gc};border-radius:12px;padding:0.2rem 1rem;">'
            f'{grade_info["grade"]}</span>'
            f'<div><span style="font-size:1.3rem;font-weight:600;">综合评分: {grade_info["score"]}/100</span><br>'
            f'<span style="color:#666;">基于收益风险比、回撤控制、胜率、盈亏比、盈利因子、卡玛比率六维度加权</span></div></div>',
            unsafe_allow_html=True,
        )

        # 雷达图
        dims = grade_info["dimensions"]
        radar_labels = list(dims.keys())
        radar_vals = [dims[k] for k in radar_labels]
        radar_vals_closed = radar_vals + [radar_vals[0]]
        radar_labels_closed = radar_labels + [radar_labels[0]]
        fig_radar = go.Figure(go.Scatterpolar(
            r=radar_vals_closed, theta=radar_labels_closed,
            fill='toself', fillcolor='rgba(31,119,180,0.15)',
            line=dict(color='#1f77b4', width=2),
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False, height=350, margin=dict(t=30, b=30),
            title="策略多维度评分",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # 指标说明
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

        # 净值曲线 + 回撤曲线 (双Y轴)
        equity_json = best.get("equity_json")
        equity_series = None
        if equity_json and equity_json != "{}" and equity_json != "null":
            try:
                equity_series = pd.read_json(equity_json, typ='series').sort_index()
            except Exception:
                pass

        if equity_series is not None and len(equity_series) > 1:
            st.markdown("#### 净值与回撤曲线")
            st.caption("蓝线为策略净值走势（左轴），红色填充区域为回撤幅度（右轴）。回撤越深表示当时离历史最高点跌得越多。")
            eq_norm = equity_series / equity_series.iloc[0] * 100
            cummax = eq_norm.cummax()
            drawdown = (eq_norm - cummax) / cummax * 100

            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=eq_norm.index, y=eq_norm.values,
                name="净值", line=dict(color="#1f77b4", width=2),
                yaxis="y1",
            ))
            fig_eq.add_trace(go.Scatter(
                x=drawdown.index, y=drawdown.values,
                name="回撤 (%)", fill="tozeroy",
                fillcolor="rgba(255,0,0,0.12)",
                line=dict(color="rgba(255,0,0,0.5)", width=1),
                yaxis="y2",
            ))
            fig_eq.update_layout(
                yaxis=dict(title="净值 (起始=100)", side="left"),
                yaxis2=dict(title="回撤 (%)", side="right", overlaying="y",
                            range=[min(drawdown.min() * 1.5, -5), 5]),
                height=420, hovermode="x unified", legend=dict(x=0, y=1.1, orientation="h"),
            )
            st.plotly_chart(fig_eq, use_container_width=True)

            # 滚动夏普比率
            st.markdown("#### 滚动夏普比率 (60日)")
            st.caption("展示策略夏普比率随时间变化的稳定性。曲线平稳说明策略在不同市况下表现一致。")
            rolling_sharpe = get_rolling_sharpe(equity_series, window=60)
            if len(rolling_sharpe) > 0:
                fig_rs = go.Figure()
                fig_rs.add_trace(go.Scatter(
                    x=rolling_sharpe.index, y=rolling_sharpe.values,
                    line=dict(color="#1f77b4", width=1.5),
                    name="滚动夏普(60日)",
                ))
                fig_rs.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
                fig_rs.add_hline(y=1, line_dash="dot", line_color="green", opacity=0.4,
                                 annotation_text="夏普=1")
                fig_rs.update_layout(height=350, yaxis_title="年化夏普比率",
                                     hovermode="x unified")
                st.plotly_chart(fig_rs, use_container_width=True)

            # 收益分布直方图
            st.markdown("#### 日收益率分布")
            st.caption("蓝色柱状图为实际日收益率分布，红色曲线为对应正态分布。")
            daily_returns = equity_series.pct_change().dropna()
            if len(daily_returns) > 10:
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(
                    x=daily_returns.values * 100, nbinsx=80,
                    name="实际分布", marker_color="rgba(31,119,180,0.6)",
                    histnorm="probability density",
                ))
                x_range = np.linspace(daily_returns.min() * 100, daily_returns.max() * 100, 200)
                from scipy.stats import norm
                mu, sigma = daily_returns.mean() * 100, daily_returns.std() * 100
                fig_dist.add_trace(go.Scatter(
                    x=x_range, y=norm.pdf(x_range, mu, sigma),
                    name="正态分布", line=dict(color="red", width=2, dash="dash"),
                ))
                fig_dist.update_layout(
                    xaxis_title="日收益率 (%)", yaxis_title="概率密度",
                    height=350, showlegend=True,
                )
                st.plotly_chart(fig_dist, use_container_width=True)
        else:
            st.info("💡 净值曲线数据不可用（旧版回测记录不含此数据，重新运行回测即可生成）。")

        # 基准对比
        st.markdown("#### 基准对比")
        st.caption('💡 **基准**是指在回测期间内、对目标指数实行"买入并持有不动"的策略表现。')
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

        # 年度收益拆解 + 月度热力图
        monthly_json = best.get("monthly_returns_json", "{}")
        monthly_df = None
        if monthly_json and monthly_json != "{}":
            try:
                monthly_df = pd.read_json(monthly_json)
            except Exception:
                pass

        if monthly_df is not None and not monthly_df.empty:
            if "全年" in monthly_df.columns:
                st.markdown("#### 年度收益拆解")
                st.caption("每根柱子代表该年的总收益率。绿色盈利，红色亏损。")
                annual = monthly_df["全年"] * 100
                colors = ["#2e7d32" if v >= 0 else "#c62828" for v in annual.values]
                fig_annual = go.Figure(go.Bar(
                    x=[str(y) for y in annual.index], y=annual.values,
                    marker_color=colors, text=[f"{v:.1f}%" for v in annual.values],
                    textposition="outside",
                ))
                fig_annual.update_layout(
                    title="年度收益率 (%)", yaxis_title="收益率 (%)",
                    height=350, xaxis_title="年份",
                )
                fig_annual.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
                st.plotly_chart(fig_annual, use_container_width=True)

            # 月度收益热力图
            st.markdown("#### 月度收益热力图")
            st.caption("🟢 绿色 = 当月盈利；🔴 红色 = 当月亏损；颜色越深表示幅度越大。")
            plot_data = monthly_df.drop(columns=["全年"], errors="ignore") * 100
            fig = px.imshow(
                plot_data, text_auto=".1f",
                color_continuous_scale="RdYlGn",
                color_continuous_midpoint=0,
                labels=dict(x="月份", y="年份", color="收益率(%)"),
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        # 交易统计与连续盈亏
        trade_json = best.get("trade_log_json", "{}")
        trade_df = None
        if trade_json and trade_json != "{}":
            try:
                trade_df = pd.read_json(trade_json)
            except Exception:
                pass

        if trade_df is not None and not trade_df.empty:
            streaks = get_streak_stats(trade_df)
            if any(v > 0 for v in streaks.values()):
                st.markdown("#### 连续盈亏统计")
                st.caption("衡量策略的连胜/连亏特征。连续亏损次数越多，对交易者心理压力越大。")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("最大连续盈利", f"{streaks['max_win_streak']} 笔")
                s2.metric("最大连续亏损", f"{streaks['max_loss_streak']} 笔")
                s3.metric("平均连续盈利", f"{streaks['avg_win_streak']} 笔")
                s4.metric("平均连续亏损", f"{streaks['avg_loss_streak']} 笔")

            for _tcol in ["买入时间", "卖出时间"]:
                if _tcol in trade_df.columns:
                    trade_df[_tcol] = pd.to_datetime(
                        trade_df[_tcol], unit="ms", errors="coerce"
                    ).dt.strftime("%Y-%m-%d")

            # 增加累计收益率列
            if "收益率" in trade_df.columns:
                _returns = trade_df["收益率"].fillna(0)
                trade_df["累计收益率"] = ((1 + _returns).cumprod() - 1)
                # 格式化
                trade_df["累计收益率"] = trade_df["累计收益率"].apply(lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "")
            if "盈亏金额" in trade_df.columns:
                trade_df["累计盈亏"] = trade_df["盈亏金额"].cumsum()

            st.markdown("#### 交易记录")
            st.dataframe(trade_df, use_container_width=True, hide_index=True)

        # --- 关注此策略（添加到组合） ---
        st.markdown("---")
        etf_sym = run_info.get("etf_symbol", "")
        etf_nm = run_info.get("etf_name", "")
        strat_name = best.get("strategy_name", "")
        if etf_sym and strat_name:
            if not storage.is_in_watchlist(etf_sym, strat_name):
                if st.button(
                    f"⭐ 关注此策略并加入组合「{strat_name}」— {etf_nm}（{etf_sym}）",
                    type="primary", key="_rpt_watch_strat",
                ):
                    storage.add_to_watchlist(etf_sym, etf_nm, strategy_name=strat_name, run_id=selected_id)
                    st.success(f"已关注 {etf_nm}（{etf_sym}）的策略「{strat_name}」！首页可查看今日信号。")
                    st.rerun()
            else:
                st.caption(f"⭐ 已关注：{etf_nm}（{etf_sym}）「{strat_name}」")

        st.caption("💡 以上结果基于历史数据回测，不代表未来收益。投资有风险，入市需谨慎。")
