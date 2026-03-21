"""
ETF 择时决策助手 — 今日信号仪表盘（Streamlit 主入口）

首页默认为空，用户回测后可将 ETF 加入关注列表，
首页对关注列表中的 ETF 展示信号分析（实时获取数据，网络失败时自动代理重试）。
"""

import sys
import os
import glob
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ui_utils
import storage

st.set_page_config(
    page_title="RICH · ETF 择时助手",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

ui_utils.render_nav("home")


# ============================================================
# 实时数据获取（直连 → 代理重试 → 本地缓存兜底）
# ============================================================
_PROXY_PORTS = [12334, 7890, 10809]  # 常见本地代理端口

def _apply_proxy_env(proxy_url):
    saved = {}
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        saved[var] = os.environ.pop(var, "")
    if proxy_url:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url
    else:
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        # 强制绕过系统代理（Windows TUN 模式下 getproxies 仍会返回代理）
        import urllib.request as _ur
        saved["_orig_getproxies"] = _ur.getproxies
        _ur.getproxies = lambda: {}
    return saved

def _restore_proxy_env(saved):
    _orig_gp = saved.pop("_orig_getproxies", None)
    if _orig_gp is not None:
        import urllib.request as _ur
        _ur.getproxies = _orig_gp
    for var, val in saved.items():
        if val:
            os.environ[var] = val
        else:
            os.environ.pop(var, None)

def _standardize_cols(df):
    col_map = {"日期": "date", "时间": "date", "开盘": "open", "收盘": "close",
               "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"}
    df = df.rename(columns=col_map)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df = df.sort_index()
    cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    return df[cols].astype(float)

def _load_cached_data(symbol: str):
    """从 data/cache 中找已有缓存文件，兜底用"""
    cache_dir = os.path.join(ROOT, "data", "cache")
    if not os.path.isdir(cache_dir):
        return None
    patterns = [
        os.path.join(cache_dir, f"{symbol}_*_qfq.csv"),
        os.path.join(cache_dir, f"{symbol}_*_index.csv"),
    ]
    cached_files = []
    for p in patterns:
        cached_files.extend(glob.glob(p))
    for cf in cached_files:
        try:
            df = pd.read_csv(cf, index_col="date", parse_dates=True)
            if len(df) >= 60:
                return df
        except Exception:
            continue
    return None

@st.cache_data(ttl=300, show_spinner="正在获取实时数据...")
def _fetch_realtime_data(symbol: str):
    """
    实时获取 ETF 数据。
    策略：直连 → 逐个代理端口重试 → 本地缓存兜底。
    """
    import akshare as ak

    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y%m%d")
    start_dt = pd.Timestamp(start_str)
    end_dt = pd.Timestamp(end_str)

    def _try_fetch(conn_mode):
        saved = _apply_proxy_env(conn_mode)
        try:
            # 方法1: Sina ETF接口（不依赖 push2his.eastmoney.com，兼容性最好）
            for _prefix in ["sh", "sz"]:
                try:
                    raw = ak.fund_etf_hist_sina(symbol=f"{_prefix}{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            return df
                except Exception:
                    pass
            # 方法2: 东方财富 ETF 接口
            try:
                raw = ak.fund_etf_hist_em(
                    symbol=symbol, period="daily",
                    start_date=start_str, end_date=end_str, adjust="qfq",
                )
                if raw is not None and len(raw) > 0:
                    return _standardize_cols(raw)
            except Exception:
                pass
            # 方法3: A 股通用接口
            try:
                raw = ak.stock_zh_a_hist(
                    symbol=symbol, period="daily", adjust="qfq",
                    start_date=start_str, end_date=end_str,
                )
                if raw is not None and len(raw) > 0:
                    return _standardize_cols(raw)
            except Exception:
                pass
            # 方法4: 腾讯指数日线
            for prefix in ("sh", "sz"):
                try:
                    raw = ak.stock_zh_index_daily_tx(symbol=f"{prefix}{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            return df
                except Exception:
                    pass
            return None
        finally:
            _restore_proxy_env(saved)

    # 1) 直连
    df = _try_fetch(None)
    if df is not None and len(df) >= 60:
        return df

    # 2) 代理重试
    for port in _PROXY_PORTS:
        df = _try_fetch(f"http://127.0.0.1:{port}")
        if df is not None and len(df) >= 60:
            return df

    # 3) 本地缓存兜底
    return _load_cached_data(symbol)


# ============================================================
# 获取关注列表
# ============================================================
watchlist_df = storage.get_watchlist()

# ============================================================
# Hero 区域
# ============================================================
st.markdown("""
<div class="hero" style="padding:1.5rem 2rem;margin:0.5rem 0 1.2rem;">
  <span class="badge">ETF 择时助手</span>
  <span class="badge">29 个指标</span>
  <h1 style="font-size:1.6rem;margin-bottom:0.3rem;">📡 今日策略信号</h1>
  <p style="font-size:0.9rem;">
    在新建回测中完成回测后，将 ETF 加入关注列表，即可在此查看实时信号分析。
  </p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# 空状态：无关注 ETF
# ============================================================
if watchlist_df.empty:
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;padding:3rem 1rem;">'
        '<div style="font-size:3rem;margin-bottom:0.8rem;">📭</div>'
        '<div style="font-size:1.1rem;font-weight:600;color:#374151;margin-bottom:0.5rem;">'
        '关注列表为空</div>'
        '<div style="font-size:0.9rem;color:#6B7280;max-width:420px;margin:0 auto 1.5rem;">'
        '去 <b>新建回测</b> 运行一次回测，然后将 ETF 加入关注列表，'
        '就可以在首页看到实时信号分析。</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        st.markdown("""
<div class="feat-card">
  <h3>🔧 新建回测</h3>
  <p>完整的三阶段回测引擎，29 个指标、数百种组合。</p>
  <a class="card-link" href="/新建回测" target="_self">开始回测 →</a>
</div>
""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div class="feat-card">
  <h3>📊 策略报告</h3>
  <p>查看回测结果的详细分析，通俗易懂的风险收益解读。</p>
  <a class="card-link" href="/策略报告" target="_self">查看报告 →</a>
</div>
""", unsafe_allow_html=True)
    with col3:
        st.markdown("""
<div class="feat-card">
  <h3>📋 历史记录</h3>
  <p>管理回测记录、对比不同策略表现。</p>
  <a class="card-link" href="/历史记录" target="_self">查看历史 →</a>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="app-footer">
  基于 VectorBT · pandas-ta · AKShare 构建 &nbsp;|&nbsp; 数据来源: AKShare &nbsp;|&nbsp; 仅供研究，不构成投资建议
</div>
""", unsafe_allow_html=True)
    st.stop()


# ============================================================
# 有关注 ETF → 展示信号仪表盘
# ============================================================
from signal_interpreter import (
    get_current_signals,
    get_consensus_signal,
    classify_market_state,
    get_signal_summary,
)
from metrics_translator import signal_card_html

# ---- 关注列表选择器（主内容区 + sidebar） ----
# 构建选项：按 ETF 分组，显示策略名
wl_options = {}
for _, row in watchlist_df.iterrows():
    wl_id = row["id"]
    sym = row["etf_symbol"]
    nm = row.get("etf_name", sym)
    strat = row.get("strategy_name") or ""
    label = f"{sym} — {nm}"
    if strat:
        label += f"  [{strat}]"
    wl_options[wl_id] = label

# 主内容区：切换 ETF 下拉框
_sel_col1, _sel_col2 = st.columns([3, 1])
with _sel_col1:
    selected_wl_id = st.selectbox(
        "📡 切换关注 ETF",
        options=list(wl_options.keys()),
        format_func=lambda x: wl_options[x],
        key="_home_wl_select",
    )
with _sel_col2:
    sel_row = watchlist_df.loc[watchlist_df["id"] == selected_wl_id].iloc[0]
    selected_symbol = sel_row["etf_symbol"]
    selected_name = sel_row.get("etf_name", selected_symbol)
    selected_strategy = sel_row.get("strategy_name") or ""
    selected_run_id = sel_row.get("run_id")
    if st.button("❌ 取消关注", key="_home_unwatch"):
        storage.remove_from_watchlist(selected_symbol, strategy_name=selected_strategy if selected_strategy else None)
        st.rerun()

etf_code = selected_symbol
etf_name = selected_name

# ---- 加载实时数据 ----
df = _fetch_realtime_data(etf_code)

if df is None or len(df) < 60:
    st.warning(
        f"⚠️ **{etf_name}（{etf_code}）** 无法获取足够的数据（已尝试直连与代理）。\n\n"
        f"请先到 **新建回测** 对该 ETF 运行一次回测，系统会自动缓存数据。"
    )

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.markdown("""
<div class="feat-card">
  <h3>🔧 新建回测</h3>
  <p>完整的三阶段回测引擎。</p>
  <a class="card-link" href="/新建回测" target="_self">去回测 →</a>
</div>
""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
<div class="feat-card">
  <h3>📋 历史记录</h3>
  <p>管理回测记录、对比策略表现。</p>
  <a class="card-link" href="/历史记录" target="_self">查看历史 →</a>
</div>
""", unsafe_allow_html=True)
    st.stop()


# ---- ETF 信号标题 ----
strat_badge = ""
if selected_strategy:
    strat_badge = (
        f'<span style="display:inline-block;background:#6366F1;color:#fff;padding:2px 10px;'
        f'border-radius:6px;font-size:0.78rem;margin-left:0.5rem;">策略: {selected_strategy}</span>'
    )

st.markdown(f"""
<div style="background:#EEF2FF;border:1.5px solid #E0E7FF;border-radius:12px;
     padding:0.8rem 1.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem;">
  <div style="font-size:1.8rem;">📡</div>
  <div>
    <div style="font-size:1.2rem;font-weight:700;color:#1E1B4B;">{etf_name}（{etf_code}）{strat_badge}</div>
    <div style="font-size:0.82rem;color:#6B7280;">数据区间：{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')} · 共 {len(df)} 个交易日</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- 关注策略的回测指标 ----
if selected_run_id:
    _best = storage.get_best_strategy(int(selected_run_id))
    if _best:
        _core = _best.get("core_metrics", {})
        _ar = _core.get("年化收益率", 0)
        _md = _core.get("最大回撤", 0)
        _sp = _core.get("夏普比率", 0)
        _wr = _core.get("胜率", 0)
        _ar_color = "#10B981" if _ar > 0 else "#EF4444"
        st.markdown(f"""
<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;
     padding:0.6rem 1.2rem;margin-bottom:1rem;">
  <div style="font-size:0.82rem;color:#6B7280;margin-bottom:0.3rem;">📊 关注策略回测表现 · <b>{_best.get('strategy_name', '')}</b></div>
  <div style="display:flex;gap:2rem;flex-wrap:wrap;">
    <span>年化收益 <b style="color:{_ar_color};">{_ar:.1f}%</b></span>
    <span>最大回撤 <b style="color:#EF4444;">{abs(_md):.1f}%</b></span>
    <span>夏普比率 <b>{_sp:.2f}</b></span>
    <span>胜率 <b>{_wr:.1f}%</b></span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- 计算信号 ----
signals = get_current_signals(df)
consensus = get_consensus_signal(signals)
market = classify_market_state(df)
summary = get_signal_summary(signals)

# ---- 市场状态横幅 ----
st.markdown(f"""
<div class="market-banner" style="background:{market['color']}15;border:1.5px solid {market['color']}40;">
  <div class="mb-icon">{market['icon']}</div>
  <div class="mb-text">
    <div class="mb-state" style="color:{market['color']};">当前市场：{market['state']}</div>
    <div class="mb-desc" style="color:#4B5563;">{market['description']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- 核心信号卡片 ----
st.markdown(signal_card_html(consensus["action"], consensus["confidence"], consensus["reason"]),
            unsafe_allow_html=True)

# ---- 信号统计概览 ----
data_date = df.index[-1].strftime("%Y-%m-%d")
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("最新收盘价", f"¥{df['close'].iloc[-1]:.3f}")
col_b.metric("📈 买入信号", f"{consensus['buy_count']} 个")
col_c.metric("📉 卖出信号", f"{consensus['sell_count']} 个")
col_d.metric("⏸️ 持有/无信号", f"{consensus['hold_count']} 个")

st.caption(f"📅 数据截至 {data_date}  ·  共分析 {len(signals)} 个技术指标  ·  实时获取（5 分钟缓存）")

# ---- 指标信号明细（可折叠）----
with st.expander("🔍 查看各指标信号明细", expanded=False):
    if summary["buy"]:
        st.markdown("#### 🟢 买入信号")
        buy_cols = st.columns(3)
        for i, s in enumerate(summary["buy"]):
            with buy_cols[i % 3]:
                st.markdown(f"""
<div class="signal-card">
  <div class="sig-name">{s['name']}</div>
  <div class="sig-action" style="color:#10B981;">🟢 买入</div>
</div>""", unsafe_allow_html=True)

    if summary["sell"]:
        st.markdown("#### 🔴 卖出信号")
        sell_cols = st.columns(3)
        for i, s in enumerate(summary["sell"]):
            with sell_cols[i % 3]:
                st.markdown(f"""
<div class="signal-card">
  <div class="sig-name">{s['name']}</div>
  <div class="sig-action" style="color:#EF4444;">🔴 卖出</div>
</div>""", unsafe_allow_html=True)

    if summary["hold"]:
        st.markdown("#### ⚪ 持有/无信号")
        hold_cols = st.columns(3)
        for i, s in enumerate(summary["hold"]):
            with hold_cols[i % 3]:
                st.markdown(f"""
<div class="signal-card">
  <div class="sig-name">{s['name']}</div>
  <div class="sig-action" style="color:#6B7280;">⏸ 持有</div>
</div>""", unsafe_allow_html=True)


# ---- 快速操作区 ----
st.markdown("---")
st.markdown(ui_utils.section_header("下一步"), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="medium")
with col1:
    st.markdown("""
<div class="feat-card">
  <h3>� 新建回测</h3>
  <p>完整的三阶段回测引擎，29 个指标、数百种组合。</p>
  <a class="card-link" href="/新建回测" target="_self">开始回测 →</a>
</div>
""", unsafe_allow_html=True)
with col2:
    st.markdown("""
<div class="feat-card">
  <h3>📊 策略报告</h3>
  <p>查看回测结果的详细分析，通俗易懂的风险收益解读。</p>
  <a class="card-link" href="/策略报告" target="_self">查看报告 →</a>
</div>
""", unsafe_allow_html=True)
with col3:
    st.markdown("""
<div class="feat-card">
  <h3>📋 历史记录</h3>
  <p>管理回测记录、对比不同策略表现。</p>
  <a class="card-link" href="/历史记录" target="_self">查看历史 →</a>
</div>
""", unsafe_allow_html=True)

# ---- Footer ----
st.markdown("""
<div class="app-footer">
  基于 VectorBT · pandas-ta · AKShare 构建 &nbsp;|&nbsp; 数据来源: AKShare &nbsp;|&nbsp; 仅供研究，不构成投资建议
</div>
""", unsafe_allow_html=True)
