"""
新建回测页面 — 自定义参数并运行三阶段回测
"""

import sys
import os
import time
import itertools
import warnings
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import storage

# ---- 历史参数预填充（必须在所有 sidebar 控件渲染前执行）----
_apply = st.session_state.pop("_params_to_apply", None)
if _apply:
    for _k, _v in _apply.items():
        st.session_state[_k] = _v

st.set_page_config(page_title="新建回测", page_icon="🚀", layout="wide")
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
    <a href="/新建回测" target="_self" class="active">🚀 新建回测</a>
    <a href="/查看结果" target="_self">📊 查看结果</a>
    <a href="/历史记录" target="_self">📚 历史记录</a>
</div>
""", unsafe_allow_html=True)
st.header("🚀 新建回测")

# ============================================================
# 常用 ETF 列表
# ============================================================
COMMON_ETFS = {
    "510300": "华泰柏瑞沪深300ETF",
    "510500": "南方中证500ETF",
    "510050": "华夏上证50ETF",
    "159915": "易方达创业板ETF",
    "159919": "嘉实沪深300ETF",
    "512100": "南方中证1000ETF",
    "518880": "华安黄金ETF",
    "513100": "国泰纳斯达克100ETF",
    "159941": "广发纳指100ETF",
    "512010": "易方达沪深300医药ETF",
}

BENCHMARK_MAP = {
    "510300": "000300", "159919": "000300",
    "510500": "000905", "510050": "000016",
    "159915": "399006", "512100": "000852",
    "518880": "518880", "513100": "513100",
    "159941": "159941", "512010": "512010",
}

# 常用指数（直接回测指数行情，不需要ETF）
COMMON_INDICES = {
    "000300": "沪深300",
    "000905": "中证500",
    "000016": "上证50",
    "399006": "创业板指",
    "000852": "中证1000",
    "000001": "上证指数",
    "399001": "深证成指",
    "000688": "科创50",
    "899050": "北证50",
}

# ============================================================
# 侧边栏参数面板
# ============================================================
st.sidebar.header("回测参数配置")

# 加载历史参数
with st.sidebar.expander("📋 加载历史回测参数"):
    _hist_runs = storage.list_runs()
    _hist_done = (
        _hist_runs[_hist_runs["status"] == "completed"]
        if not _hist_runs.empty else pd.DataFrame()
    )
    if not _hist_done.empty:
        _load_opts = {
            row["id"]: f"#{row['id']} {row['etf_symbol']} ({row['start_date']}~{row['end_date']})"
            for _, row in _hist_done.head(20).iterrows()
        }
        _sel_load_id = st.selectbox(
            "选择记录", list(_load_opts.keys()),
            format_func=lambda x: _load_opts[x],
            key="_load_run_selector",
            label_visibility="collapsed",
        )
        if st.button("📥 填充到下方参数面板", use_container_width=True, key="_load_btn"):
            from datetime import datetime as _dt
            _r = storage.get_run(_sel_load_id)
            _ep = _r.get("extra_params", {})
            _sym = _r.get("etf_symbol", "510300")
            _is_idx = _ep.get("is_index_mode", _sym in COMMON_INDICES)
            _params = {"_sb_target_type": "指数" if _is_idx else "ETF基金"}
            if _is_idx:
                if _sym in COMMON_INDICES:
                    _params["_sb_idx_mode"] = "常用指数"
                    _params["_sb_idx_select"] = _sym
                else:
                    _params["_sb_idx_mode"] = "自定义代码"
                    _params["_sb_idx_code"] = _sym
                    _params["_sb_idx_name"] = _r.get("etf_name", "")
            else:
                if _sym in COMMON_ETFS:
                    _params["_sb_etf_mode"] = "常用ETF"
                    _params["_sb_etf_select"] = _sym
                else:
                    _params["_sb_etf_mode"] = "自定义代码"
                    _params["_sb_etf_code"] = _sym
                    _params["_sb_etf_name"] = _r.get("etf_name", "")
                    _params["_sb_bench_code"] = _r.get("benchmark_symbol", "000300")
            try:
                _params["_sb_start_date"] = _dt.strptime(_r["start_date"], "%Y%m%d").date()
                _params["_sb_end_date"] = _dt.strptime(_r["end_date"], "%Y%m%d").date()
            except Exception:
                pass
            _params["_sb_data_freq"] = _r.get("data_freq", "daily")
            _params["_sb_init_cash"] = int(_r.get("init_cash") or 100000)
            _params["_sb_slippage"] = float(_ep.get("slippage", 0.10))
            _params["_sb_commission"] = float(_ep.get("commission", 0.02))
            _params["_sb_stamp_tax"] = float(_ep.get("stamp_tax", 0.05))
            _params["_sb_data_adjust"] = _ep.get("data_adjust", "qfq")
            _params["_sb_phase2_top_n"] = int(_ep.get("phase2_top_n", 10))
            _params["_sb_phase2_min_sharpe"] = float(_ep.get("phase2_min_sharpe", 1.0))
            _params["_sb_phase2_max_dd"] = float(_ep.get("phase2_max_dd", 30.0))
            st.session_state["_params_to_apply"] = _params
            st.rerun()
    else:
        st.caption("暂无已完成的回测记录")

# 标的类型选择
st.sidebar.subheader("📌 标的配置")
target_type = st.sidebar.radio(
    "标的类型", ["ETF基金", "指数"], horizontal=True, key="_sb_target_type",
    help=(
        "**ETF基金**：在交易所上市的基金，跟踪某个指数，可像股票一样买卖。"
        "含管理费（约 0.1%~0.5%/年），历史数据从成立日起。\n\n"
        "**指数**：直接对指数点位回测，无管理费摩擦，历史数据更长（最早可追溯至指数发布日），"
        "适合评估策略在理论市场中的长期表现。"
    ),
)

if target_type == "ETF基金":
    etf_mode = st.sidebar.radio("选择方式", ["常用ETF", "自定义代码"], horizontal=True, key="_sb_etf_mode")
    if etf_mode == "常用ETF":
        etf_symbol = st.sidebar.selectbox(
            "目标ETF",
            list(COMMON_ETFS.keys()),
            format_func=lambda x: f"{x} - {COMMON_ETFS[x]}",
            key="_sb_etf_select",
            help="选择要回测的 ETF 基金。代码为6位数字，数据来源腾讯/东方财富。",
        )
        etf_name = COMMON_ETFS[etf_symbol]
        benchmark_symbol = BENCHMARK_MAP.get(etf_symbol, "000300")
    else:
        etf_symbol = st.sidebar.text_input("ETF代码", value="510300", key="_sb_etf_code",
            help="6位数字ETF代码，如 510300（沪深300ETF）、159915（创业板ETF）。")
        etf_name = st.sidebar.text_input("ETF名称", value="沪深300ETF", key="_sb_etf_name")
        benchmark_symbol = st.sidebar.text_input("基准指数代码", value="000300", key="_sb_bench_code",
            help="用于对比策略收益的参照指数，通常选该ETF跟踪的指数。\n沪深300→000300，中证500→000905，创业板→399006。")
    is_index_mode = False
else:
    idx_mode = st.sidebar.radio("选择方式", ["常用指数", "自定义代码"], horizontal=True, key="_sb_idx_mode")
    if idx_mode == "常用指数":
        etf_symbol = st.sidebar.selectbox(
            "目标指数",
            list(COMMON_INDICES.keys()),
            format_func=lambda x: f"{x} - {COMMON_INDICES[x]}",
            key="_sb_idx_select",
            help="选择要回测的 A 股指数。指数点位直接反映市场，无 ETF 折溢价和管理费影响。",
        )
        etf_name = COMMON_INDICES[etf_symbol]
    else:
        etf_symbol = st.sidebar.text_input("指数代码", value="000300", key="_sb_idx_code",
            help="6位指数代码。沪市以0开头，如000300（沪深300）；深市以3或3或9开头，如399006（创业板指）。")
        etf_name = st.sidebar.text_input("指数名称", value="沪深300", key="_sb_idx_name")
    benchmark_symbol = etf_symbol  # 指数模式下基准与标的相同
    is_index_mode = True

# 时间范围
st.sidebar.subheader("📅 回测周期")
col_s, col_e = st.sidebar.columns(2)
from datetime import date, datetime
with col_s:
    start_date = st.date_input("起始日期", value=date(2018, 1, 1), min_value=date(2005, 1, 1),
        key="_sb_start_date",
        help="回测的起始时间。建议至少覆盖一个完整牛熊市周期（3~5年），周期越长结果越有统计意义。")
with col_e:
    end_date = st.date_input("结束日期", value=date(2023, 12, 31), max_value=date(2026, 12, 31),
        key="_sb_end_date",
        help="回测的结束时间。历史回测结果不代表未来实际收益，仅供参考。")

# 数据频率
st.sidebar.subheader("⏱️ 数据频率")
data_freq = st.sidebar.selectbox(
    "K线频率", ["daily", "weekly"], index=0,
    format_func=lambda x: {"daily": "日线", "weekly": "周线"}[x],
    key="_sb_data_freq",
    help=(
        "**日线**：每个交易日产生一条信号，交易更频繁，对短期趋势敏感，但手续费摩擦较高。\n\n"
        "**周线**：每周产生一条信号，交易次数少，适合中长期趋势策略，手续费损耗更低，信号更稳定。"
    ),
)

# 资金与费率
st.sidebar.subheader("💰 资金与费率")
init_cash = st.sidebar.number_input(
    "初始资金 (元)", value=100000, min_value=10000, step=10000, key="_sb_init_cash",
    help="模拟账户起始本金。收益率与本金大小无关，但会影响每笔手续费的绝对金额（资金越小，手续费占比越大）。",
)
slippage = st.sidebar.number_input(
    "滑点 (%)", value=0.10, min_value=0.0, step=0.01, format="%.2f", key="_sb_slippage",
    help=(
        "**滑点**：下单时预期价格与实际成交价格之间的差距，由市场流动性不足或行情快速波动导致。\n\n"
        "ETF 流动性较好，通常 0.05%~0.1%；小盘或波动剧烈时可适当调高。"
    ),
)
commission = st.sidebar.number_input(
    "佣金 (%)", value=0.02, min_value=0.0, step=0.01, format="%.2f", key="_sb_commission",
    help=(
        "**佣金**：每次买入或卖出支付给券商的手续费，买卖各收一次。\n\n"
        "主流券商 ETF 佣金约 0.015%~0.025%，部分互联网券商可免收，请以实际合同为准。"
    ),
)
stamp_tax = st.sidebar.number_input(
    "印花税 (%)", value=0.05, min_value=0.0, step=0.01, format="%.2f", key="_sb_stamp_tax",
    help=(
        "**印花税**：由国家征收，**仅卖出时收取，买入不收**。\n\n"
        "当前 A 股股票印花税为 **0.05%**（2023年8月起）。\n"
        "**ETF 基金不征印花税，可填 0**。"
    ),
)

entry_fees = (slippage + commission) / 100
exit_fees = (slippage + commission + stamp_tax) / 100

st.sidebar.caption(f"买入费率: {entry_fees*100:.2f}% | 卖出费率: {exit_fees*100:.2f}%")

# 复权方式
data_adjust = st.sidebar.selectbox(
    "复权方式", ["qfq", "hfq", ""],
    format_func=lambda x: {"qfq": "前复权", "hfq": "后复权", "": "不复权"}[x],
    key="_sb_data_adjust",
    help=(
        "**前复权**（推荐）：以最新价格为基准向前调整历史价格，使历史走势平滑衔接，"
        "技术指标计算不受分红/拆分干扰，**适合策略回测**。\n\n"
        "**后复权**：以最初价格为基准向后累积调整，价格随时间增大，"
        "适合计算买入持有的理论总收益。\n\n"
        "**不复权**：使用原始历史价格，遇分红/拆分时出现人为价格跳空，"
        "会干扰技术指标信号，**不建议用于回测**。"
    ),
)

# 阶段二参数
st.sidebar.subheader("⚙️ 筛选阈值")
phase3_mode = st.sidebar.radio(
    "阶段三优化目标", ["自动（夏普最高）", "手动选择"],
    horizontal=True, key="_sb_phase3_mode",
    help=(
        "**自动**：一键完成全部三阶段，自动对夏普比率最高的策略进行参数优化。\n\n"
        "**手动选择**：先完成阶段一、二，然后从所有候选策略中自选一个进行阶段三参数优化。"
        "适合你对某个特定策略感兴趣，而非仅看夏普排名。"
    ),
)
phase2_top_n = st.sidebar.slider(
    "阶段二: 取TOP N组合", 3, 20, 10, key="_sb_phase2_top_n",
    help=(
        "**回测流程说明**：\n"
        "- 阶段一：对所有技术指标单独回测，按夏普比率排名\n"
        "- 阶段二：从阶段一中取前 N 名，两两组合（AND/OR逻辑）再次回测\n"
        "- 阶段三：对阶段二最优组合进行参数敏感性扫描\n\n"
        "N 值越大，候选组合越多、耗时越长，建议设 **8~12**。"
    ),
)
phase2_min_sharpe = st.sidebar.number_input(
    "阶段二: 最低夏普", value=1.0, step=0.1, format="%.1f", key="_sb_phase2_min_sharpe",
    help=(
        "**夏普比率（Sharpe Ratio）**：每承担一单位风险所获得的超额收益，数值越高越好。\n\n"
        "参考标准：\n"
        "- **> 2**：优秀，风险调整后收益很高\n"
        "- **1~2**：良好，可接受\n"
        "- **0~1**：较差，收益与风险不成比例\n"
        "- **< 0**：策略整体亏损\n\n"
        "此处为进入阶段三的**最低门槛**，低于此值的组合直接淘汰，建议设 **1.0~1.5**。"
    ),
)
phase2_max_dd = st.sidebar.number_input(
    "阶段二: 最大回撤 (%)", value=30.0, step=5.0, format="%.0f", key="_sb_phase2_max_dd",
    help=(
        "**最大回撤（Max Drawdown）**：从历史最高净值跌到随后最低点的跌幅，"
        "衡量策略的最坏亏损情况，数值越低越好。\n\n"
        "参考标准：\n"
        "- **< 10%**：风险极低，适合保守型\n"
        "- **10%~20%**：可接受，多数投资者能承受\n"
        "- **> 30%**：心理压力较大，需要较强持仓信心\n\n"
        "此处为允许进入阶段三的**回撤上限**，超过此值的组合被淘汰。"
    ),
)

# 网络代理
st.sidebar.subheader("🌐 网络代理")
proxy_mode = st.sidebar.radio(
    "代理设置", ["直连（绕过代理）", "使用本地代理"], horizontal=True,
    help=(
        "**直连**：绕过系统代理直接请求数据源，适合大多数家庭网络环境（默认推荐）。\n\n"
        "**本地代理**：若直连失败（如公司网络/防火墙限制），"
        "可使用 Clash/V2Ray 等工具的本地 HTTP 代理转发请求。"
    ),
)
proxy_url = None
if proxy_mode == "使用本地代理":
    proxy_port = st.sidebar.number_input(
        "本地代理端口", value=12334, min_value=1, max_value=65535, step=1,
        help="本地代理工具监听的端口号。Clash 默认 7890，V2Ray 默认 10809，请以实际工具配置为准。",
    )
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    st.sidebar.caption(f"代理地址: {proxy_url}")

# 备注
notes = st.sidebar.text_area("备注", placeholder="本次回测说明...")


# ============================================================
# 数据获取（带参数化）
# ============================================================

def _apply_proxy(proxy_url):
    """
    设置代理环境变量。
    proxy_url=None  → 直连模式，清除所有代理并设 NO_PROXY=*
    proxy_url=str   → 使用指定代理
    返回 saved dict 供还原。
    """
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
        # 直连：显式告知 requests/urllib3 对所有 host 跳过系统代理
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
    return saved


def _restore_proxy(saved):
    for var, val in saved.items():
        if val:
            os.environ[var] = val
        else:
            os.environ.pop(var, None)


def _standardize_cols(df):
    col_map = {"日期": "date", "开盘": "open", "收盘": "close",
               "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"}
    df = df.rename(columns=col_map)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df = df.sort_index()
    cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    return df[cols].astype(float)


def _find_any_cache(cache_dir, sym, suffix):
    """查找同symbol任意日期范围的缓存文件（用于日期缩窄场景）"""
    import glob
    pattern = os.path.join(cache_dir, f"{sym}_*{suffix}.csv")
    files = glob.glob(pattern)
    return files[0] if files else None


def fetch_data_dynamic(etf_sym, bench_sym, start, end, adjust, freq,
                       is_index=False, proxy_url=None):
    """动态获取数据，支持ETF/指数双模式、代理配置与宽松缓存复用"""
    import akshare as ak

    cache_dir = os.path.join(ROOT, "data", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)

    # ---- 主标的数据 ----
    if is_index:
        # 指数模式：直接获取指数行情，缓存标记为 _index
        main_cache = os.path.join(cache_dir, f"{etf_sym}_{start_str}_{end_str}_index.csv")
        main_df = _fetch_index_df(etf_sym, start_str, end_str, start_dt, end_dt,
                                   main_cache, cache_dir, ak, proxy_url)
    else:
        # ETF模式
        main_cache = os.path.join(cache_dir, f"{etf_sym}_{start_str}_{end_str}_{adjust}.csv")
        if os.path.exists(main_cache):
            main_df = pd.read_csv(main_cache, index_col="date", parse_dates=True)
        else:
            any_cache = _find_any_cache(cache_dir, etf_sym, f"_{adjust}")
            if any_cache:
                tmp = pd.read_csv(any_cache, index_col="date", parse_dates=True)
                sliced = tmp.loc[start_dt:end_dt]
                if len(sliced) > 20:
                    main_df = sliced
                    main_df.to_csv(main_cache)
                    any_cache = "ok"
                else:
                    any_cache = None
            if not any_cache:
                main_df = _fetch_etf_df(etf_sym, start_str, end_str, start_dt, end_dt,
                                        adjust, freq, main_cache, ak, proxy_url)

    main_df = main_df.loc[start_dt:end_dt]

    # ---- 基准数据 ----
    if is_index:
        # 指数模式下基准=标的本身，直接复用
        bench_df = main_df.copy()
    else:
        bench_df = _fetch_index_df(bench_sym, start_str, end_str, start_dt, end_dt,
                                    os.path.join(cache_dir, f"{bench_sym}_{start_str}_{end_str}_index.csv"),
                                    cache_dir, ak, proxy_url)
        # 若基准实在获取不到，用主标的近似
        if bench_df is None or bench_df.empty:
            bench_df = main_df.copy()

    bench_df = bench_df.loc[start_dt:end_dt]

    # 对齐索引
    common_idx = main_df.index.intersection(bench_df.index)
    return main_df.loc[common_idx], bench_df.loc[common_idx]


def _fetch_etf_df(symbol, start_str, end_str, start_dt, end_dt,
                  adjust, freq, cache_path, ak, proxy_url):
    """获取ETF数据，多方法 fallback + 代理→直连双模式重试"""
    period = "daily" if freq == "daily" else "weekly"

    def _try_etf_one_mode(conn_mode):
        result = None
        saved = _apply_proxy(conn_mode)
        try:
            # 方法1: fund_etf_hist_em（东方财富ETF专用接口，最常用）
            try:
                raw = ak.fund_etf_hist_em(
                    symbol=symbol, period=period,
                    start_date=start_str, end_date=end_str, adjust=adjust,
                )
                if raw is not None and len(raw) > 0:
                    result = _standardize_cols(raw)
            except Exception:
                pass

            # 方法2: fund_etf_hist_sina（新浪ETF接口）
            if result is None:
                try:
                    raw = ak.fund_etf_hist_sina(symbol=f"sz{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            result = df
                except Exception:
                    pass
                if result is None:
                    try:
                        raw = ak.fund_etf_hist_sina(symbol=f"sh{symbol}")
                        if raw is not None and len(raw) > 0:
                            df = _standardize_cols(raw).loc[start_dt:end_dt]
                            if len(df) > 20:
                                result = df
                    except Exception:
                        pass

            # 方法3: 当A股通用接口（部分ETF也可通过此接口获取）
            if result is None:
                for market in ["sh", "sz"]:
                    try:
                        raw = ak.stock_zh_a_hist(
                            symbol=symbol, period=period, adjust=adjust,
                            start_date=start_str, end_date=end_str,
                        )
                        if raw is not None and len(raw) > 0:
                            result = _standardize_cols(raw)
                            break
                    except Exception:
                        pass

            # 方法4: 腾讯日线（不支持复权但可兜底）
            if result is None:
                for prefix in ["sh", "sz"]:
                    try:
                        raw = ak.stock_zh_index_daily_tx(symbol=f"{prefix}{symbol}")
                        if raw is not None and len(raw) > 0:
                            df = _standardize_cols(raw).loc[start_dt:end_dt]
                            if len(df) > 20:
                                result = df
                                break
                    except Exception:
                        pass
        finally:
            _restore_proxy(saved)
        return result

    # 优先使用用户配置的代理；若失败则直连重试
    df = _try_etf_one_mode(proxy_url)
    if (df is None or len(df) == 0) and proxy_url is not None:
        df = _try_etf_one_mode(None)

    if df is not None and not df.empty:
        df.to_csv(cache_path)
        return df
    raise RuntimeError(
        f"ETF {symbol} 数据获取失败，所有数据源均不可用。"
        "请检查代码是否正确、网络是否通畅，或尝试切换代理/直连模式。"
    )


def _fetch_index_df(symbol, start_str, end_str, start_dt, end_dt,
                    cache_path, cache_dir, ak, proxy_url):
    """获取指数数据，带缓存复用、多方法fallback、代理→直连双模式重试"""
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path, index_col="date", parse_dates=True)

    # 复用宽松缓存
    any_cache = _find_any_cache(cache_dir, symbol, "_index")
    if any_cache and any_cache != cache_path:
        tmp = pd.read_csv(any_cache, index_col="date", parse_dates=True)
        sliced = tmp.loc[start_dt:end_dt]
        if len(sliced) > 20:
            sliced.to_csv(cache_path)
            return sliced

    def _standardize_csindex(raw):
        """处理 stock_zh_index_hist_csindex 的特殊列名（成交金额≠成交额）"""
        col_map = {"日期": "date", "开盘": "open", "最高": "high",
                   "最低": "low", "收盘": "close",
                   "成交量": "volume", "成交金额": "amount"}
        df = raw.rename(columns=col_map)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        df = df.sort_index()
        cols = [c for c in ["open", "high", "low", "close", "volume", "amount"]
                if c in df.columns]
        return df[cols].astype(float)

    def _try_one_mode(conn_mode):
        result = None
        saved = _apply_proxy(conn_mode)
        try:
            # 方法1: 腾讯源 sh 前缀（最可靠，2007-今，代理/直连均可）
            try:
                raw = ak.stock_zh_index_daily_tx(symbol=f"sh{symbol}")
                if raw is not None and len(raw) > 0:
                    df = _standardize_cols(raw).loc[start_dt:end_dt]
                    if len(df) > 20:
                        result = df
            except Exception:
                pass

            # 方法2: 中证指数官网（2009-今，数据权威）
            if result is None:
                try:
                    raw = ak.stock_zh_index_hist_csindex(
                        symbol=symbol, start_date=start_str, end_date=end_str
                    )
                    if raw is not None and len(raw) > 0:
                        df = _standardize_csindex(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            result = df
                except Exception:
                    pass

            # 方法3: 腾讯源 sz 前缀（适合深市指数）
            if result is None:
                try:
                    raw = ak.stock_zh_index_daily_tx(symbol=f"sz{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            result = df
                except Exception:
                    pass

            # 方法4: 东方财富 sh 前缀
            if result is None:
                try:
                    raw = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            result = df
                except Exception:
                    pass

            # 方法5: 东方财富 sz 前缀
            if result is None:
                try:
                    raw = ak.stock_zh_index_daily_em(symbol=f"sz{symbol}")
                    if raw is not None and len(raw) > 0:
                        df = _standardize_cols(raw).loc[start_dt:end_dt]
                        if len(df) > 20:
                            result = df
                except Exception:
                    pass

            # 方法6: 东方财富 index_zh_a_hist
            if result is None:
                try:
                    raw = ak.index_zh_a_hist(symbol=symbol, period="daily",
                                             start_date=start_str, end_date=end_str)
                    if raw is not None and len(raw) > 0:
                        result = _standardize_cols(raw)
                except Exception:
                    pass

            # 方法7: 新浪源（数据可能截至 2019）
            if result is None:
                for sina_sym in [f"sh{symbol}", f"sz{symbol}"]:
                    try:
                        raw = ak.stock_zh_index_daily(symbol=sina_sym)
                        if raw is not None and len(raw) > 0:
                            df = _standardize_cols(raw).loc[start_dt:end_dt]
                            if len(df) > 20:
                                result = df
                                break
                    except Exception:
                        pass
        finally:
            _restore_proxy(saved)
        return result

    # 优先使用用户配置的代理；若全部失败则自动回退直连
    df = _try_one_mode(proxy_url)
    if (df is None or len(df) == 0) and proxy_url is not None:
        df = _try_one_mode(None)  # 直连重试

    if df is not None and not df.empty:
        df.to_csv(cache_path)
    return df


# ============================================================
# 回测执行函数
# ============================================================
def run_full_backtest(etf_df, benchmark_df, progress_bar, status_text,
                      phase3_override=None):
    """运行完整三阶段回测，返回所有结果。
    phase3_override: 若非 None，用此策略名替代自动选择的最优策略进行阶段三。
    """
    from indicators import get_all_indicators
    from engine.backtester import run_single_backtest, run_combination_backtest
    from engine.metrics import (
        calculate_core_metrics, calculate_aux_metrics,
        calculate_benchmark_metrics, get_monthly_returns, get_trade_log,
    )

    close = etf_df["close"]
    bench_close = benchmark_df["close"]
    results = {}

    # --- 基准 ---
    status_text.text("计算基准指标...")
    bench_metrics = calculate_benchmark_metrics(bench_close)
    results["bench_metrics"] = bench_metrics
    progress_bar.progress(5)

    # --- 阶段一 ---
    status_text.text("阶段一：生成指标信号...")
    all_signals = get_all_indicators(etf_df)
    progress_bar.progress(15)

    status_text.text(f"阶段一：回测 {len(all_signals)} 个策略...")
    metrics_list = []
    valid_signals = []
    for i, (entries, exits, name) in enumerate(all_signals):
        try:
            pf = run_single_backtest(close, entries, exits,
                                      init_cash=init_cash, entry_fees=entry_fees, exit_fees=exit_fees)
            m = calculate_core_metrics(pf, name)
            metrics_list.append(m)
            valid_signals.append((entries, exits, name))
        except Exception:
            pass
        if (i + 1) % 5 == 0:
            pct = 15 + int(35 * (i + 1) / len(all_signals))
            progress_bar.progress(min(pct, 50))

    phase1_df = pd.DataFrame(metrics_list)
    if not phase1_df.empty:
        phase1_df = phase1_df.sort_values("夏普比率", ascending=False).reset_index(drop=True)
    results["phase1_df"] = phase1_df
    results["phase1_metrics"] = metrics_list
    results["all_signals"] = valid_signals
    progress_bar.progress(50)

    # --- 阶段二 ---
    status_text.text("阶段二：组合策略回测...")
    top_names = phase1_df.head(phase2_top_n)["指标名称"].tolist() if not phase1_df.empty else []
    signal_map = {name: (entries, exits) for entries, exits, name in valid_signals}
    top_signals = {n: signal_map[n] for n in top_names if n in signal_map}

    combo_results = []
    if len(top_signals) >= 2:
        combos = list(itertools.combinations(top_signals.keys(), 2))
        logics = ["AND", "OR"]
        total = len(combos) * len(logics)
        for idx, ((n1, n2), logic) in enumerate(itertools.product(combos, logics)):
            e1, x1 = top_signals[n1]
            e2, x2 = top_signals[n2]
            try:
                pf = run_combination_backtest(close, e1, x1, e2, x2, logic=logic,
                                               init_cash=init_cash)
                m = calculate_core_metrics(pf, f"{n1} + {n2}")
                m["指标组合"] = f"{n1} + {n2}"
                m["逻辑"] = logic
                combo_results.append(m)
            except Exception:
                pass
            if (idx + 1) % 10 == 0:
                pct = 50 + int(25 * (idx + 1) / total)
                progress_bar.progress(min(pct, 75))

    phase2_df = pd.DataFrame(combo_results)
    if not phase2_df.empty:
        phase2_df = phase2_df.sort_values("夏普比率", ascending=False).reset_index(drop=True)
    results["phase2_df"] = phase2_df
    results["phase2_metrics"] = combo_results
    progress_bar.progress(75)

    # --- 确定最优策略 ---
    best_name = ""
    best_logic = ""
    combo_info = None

    # __SKIP__ 表示手动模式下只需阶段一二
    if phase3_override == "__SKIP__":
        results["phase3_df"] = pd.DataFrame()
        results["best_name"] = ""
        results["best_logic"] = ""
        progress_bar.progress(100)
        status_text.text("阶段一 & 二完成！请选择策略继续阶段三。")
        return results

    if phase3_override and phase3_override != "__SKIP__":
        # 手动指定的策略
        # phase3_override 格式: "名称" 或 "组合名 [AND]" / "组合名 [OR]"
        if " [AND]" in phase3_override:
            best_name = phase3_override.replace(" [AND]", "")
            best_logic = "AND"
        elif " [OR]" in phase3_override:
            best_name = phase3_override.replace(" [OR]", "")
            best_logic = "OR"
        else:
            best_name = phase3_override
    elif not phase2_df.empty:
        best_row = phase2_df.iloc[0]
        best_name = best_row.get("指标组合", best_row.get("指标名称", ""))
        best_logic = best_row.get("逻辑", "")
    elif not phase1_df.empty:
        best_row = phase1_df.iloc[0]
        best_name = best_row["指标名称"]

    # --- 阶段三 ---
    status_text.text(f"阶段三：参数优化 ({best_name})...")
    from main import _scan_indicator_params
    opt_target = best_name.split(" + ")[0].strip() if " + " in best_name else best_name
    param_df = _scan_indicator_params(etf_df, close, opt_target)
    results["phase3_df"] = param_df
    results["best_name"] = best_name
    results["best_logic"] = best_logic
    progress_bar.progress(90)

    # --- 最优策略详细分析 ---
    status_text.text("生成最优策略分析...")
    if best_name:
        if " + " in best_name and best_logic:
            parts = best_name.split(" + ")
            n1, n2 = parts[0].strip(), parts[1].strip()
            if n1 in signal_map and n2 in signal_map:
                e1, x1 = signal_map[n1]
                e2, x2 = signal_map[n2]
                pf = run_combination_backtest(close, e1, x1, e2, x2, logic=best_logic,
                                               init_cash=init_cash)
                combo_info = {"signals1": (e1, x1), "signals2": (e2, x2), "logic": best_logic}
        else:
            sig = next(((e, x, n) for e, x, n in valid_signals if n == best_name), None)
            if sig:
                pf = run_single_backtest(close, sig[0], sig[1],
                                          init_cash=init_cash, entry_fees=entry_fees, exit_fees=exit_fees)

        try:
            core = calculate_core_metrics(pf, best_name)
            aux = calculate_aux_metrics(pf)
            monthly = get_monthly_returns(pf)
            trade_log = get_trade_log(pf)
            equity = pf.value()
            if isinstance(equity, pd.DataFrame):
                equity = equity.iloc[:, 0]
            results["best_core"] = core
            results["best_aux"] = aux
            results["best_monthly"] = monthly
            results["best_trade_log"] = trade_log
            results["best_equity"] = equity
        except Exception:
            pass

    progress_bar.progress(100)
    status_text.text("回测完成！")
    return results


# ============================================================
# 结果展示函数
# ============================================================
def _show_backtest_results(results, benchmark_df):
    """展示回测结果（阶段一/二/三 + 最优策略）"""
    st.markdown("---")

    # 阶段一
    st.subheader("阶段一：单指标测试结果")
    phase1_df = results.get("phase1_df", pd.DataFrame())
    if not phase1_df.empty:
        fig = px.scatter(
            phase1_df, x="最大回撤", y="夏普比率",
            text="指标名称", color="夏普比率",
            color_continuous_scale="RdYlGn",
            title="单指标: 夏普比率 vs 最大回撤",
            hover_data=["年化收益率", "胜率", "交易次数"],
        )
        fig.update_traces(textposition="top center", textfont_size=8)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        display_cols = ["指标名称", "年化收益率", "最大回撤", "夏普比率",
                       "胜率", "盈亏比", "交易次数", "年化波动率"]
        avail_cols = [c for c in display_cols if c in phase1_df.columns]
        st.dataframe(phase1_df[avail_cols].head(20), use_container_width=True, hide_index=True)

    # 阶段二
    st.subheader("阶段二：组合策略测试结果")
    phase2_df = results.get("phase2_df", pd.DataFrame())
    if not phase2_df.empty:
        display_cols = ["指标组合", "逻辑", "年化收益率", "最大回撤", "夏普比率",
                       "胜率", "盈亏比", "交易次数"]
        avail_cols = [c for c in display_cols if c in phase2_df.columns]
        st.dataframe(phase2_df[avail_cols].head(20), use_container_width=True, hide_index=True)

    # 最优策略
    best_name = results.get("best_name", "")
    if best_name and "best_core" in results:
        st.subheader(f"最优策略: {best_name}")
        core = results["best_core"]

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("年化收益", f"{core.get('年化收益率', 0):.2f}%")
        c2.metric("夏普比率", f"{core.get('夏普比率', 0):.3f}")
        c3.metric("最大回撤", f"{core.get('最大回撤', 0):.2f}%")
        c4.metric("胜率", f"{core.get('胜率', 0):.1f}%")
        c5.metric("交易次数", f"{core.get('交易次数', 0)}")
        c6.metric("盈亏比", f"{core.get('盈亏比', 0):.2f}")

        # 收益曲线
        equity = results.get("best_equity")
        if equity is not None and benchmark_df is not None:
            bench_close = benchmark_df["close"]
            strat_norm = equity / equity.iloc[0] * 100
            bench_norm = bench_close / bench_close.iloc[0] * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=strat_norm.index, y=strat_norm.values,
                name=f"策略: {best_name}", line=dict(color="#1f77b4", width=2),
            ))
            fig.add_trace(go.Scatter(
                x=bench_norm.index, y=bench_norm.values,
                name="基准", line=dict(color="#ff7f0e", width=1.5, dash="dash"),
            ))
            fig.update_layout(title="收益曲线对比", yaxis_title="净值 (起始=100)",
                               height=450, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

        # 月度收益热力图
        monthly = results.get("best_monthly")
        if monthly is not None and not monthly.empty:
            plot_data = monthly.drop(columns=["全年"], errors="ignore") * 100
            fig = px.imshow(
                plot_data, text_auto=".1f",
                color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                title="月度收益热力图 (%)",
                labels=dict(x="月份", y="年份", color="收益率(%)"),
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        # 交易记录
        trade_log = results.get("best_trade_log")
        if trade_log is not None and not trade_log.empty:
            st.markdown("**交易记录**")
            st.dataframe(trade_log, use_container_width=True, hide_index=True)

    # 阶段三
    phase3_df = results.get("phase3_df", pd.DataFrame())
    if not phase3_df.empty:
        st.subheader("阶段三：参数敏感性")
        metric_cols = {"指标名称", "总收益率", "年化收益率", "最大回撤", "年化波动率",
                      "夏普比率", "卡玛比率", "索提诺比率", "胜率", "盈亏比",
                      "交易次数", "平均持仓天数", "年化交易频率"}
        param_cols = [c for c in phase3_df.columns if c not in metric_cols]
        if param_cols:
            fig = px.scatter(
                phase3_df, x=param_cols[0], y="夏普比率",
                color="年化收益率", size="交易次数",
                color_continuous_scale="RdYlGn",
                title=f"参数敏感性: {param_cols[0]} vs 夏普比率",
                hover_data=["年化收益率", "最大回撤", "交易次数"],
            )
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(phase3_df.head(30), use_container_width=True, hide_index=True)


# ============================================================
# 主界面
# ============================================================
st.markdown("### 参数预览")
col1, col2, col3, col4 = st.columns(4)
col1.metric("目标ETF", f"{etf_symbol} ({etf_name})")
col2.metric("回测区间", f"{start_date} ~ {end_date}")
col3.metric("初始资金", f"¥{init_cash:,.0f}")
col4.metric("数据频率", {"daily": "日线", "weekly": "周线"}[data_freq])

st.markdown("---")

# 运行按钮
_is_manual_phase3 = (phase3_mode == "手动选择")

def _run_and_save(phase3_override=None):
    """执行回测流程并保存结果到数据库"""
    start_time = time.time()

    # 创建数据库记录
    run_id = storage.create_run(
        etf_symbol=etf_symbol, etf_name=etf_name,
        benchmark_symbol=benchmark_symbol,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        data_freq=data_freq, init_cash=init_cash,
        entry_fees=entry_fees, exit_fees=exit_fees,
        notes=notes,
        extra_params={
            "target_type": target_type,
            "is_index_mode": is_index_mode,
            "slippage": slippage,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "data_adjust": data_adjust,
            "phase2_top_n": phase2_top_n,
            "phase2_min_sharpe": phase2_min_sharpe,
            "phase2_max_dd": phase2_max_dd,
        },
    )

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 获取数据
        status_text.text("正在获取数据...")
        etf_df, benchmark_df = fetch_data_dynamic(
            etf_symbol, benchmark_symbol, start_date, end_date, data_adjust, data_freq,
            is_index=is_index_mode, proxy_url=proxy_url,
        )
        progress_bar.progress(5)
        mode_label = "指数" if is_index_mode else "ETF"
        st.info(f"数据加载完成: {mode_label} {len(etf_df)} 条 | 基准 {len(benchmark_df)} 条")

        # 执行回测
        results = run_full_backtest(etf_df, benchmark_df, progress_bar, status_text,
                                    phase3_override=phase3_override)

        elapsed = time.time() - start_time

        # 保存到数据库
        storage.save_phase1(run_id, results.get("phase1_metrics", []))
        storage.save_phase2(run_id, results.get("phase2_metrics", []))
        if results.get("phase3_df") is not None and not results["phase3_df"].empty:
            storage.save_phase3(run_id, results.get("best_name", ""), results["phase3_df"])
        if "best_core" in results:
            bench_m = results.get("bench_metrics", {})
            storage.save_best_strategy(
                run_id, results.get("best_name", ""),
                results["best_core"], results.get("best_aux", {}),
                bench_m,
                results.get("best_monthly"), results.get("best_trade_log"),
                results.get("best_equity"),
            )
        storage.update_run_status(run_id, "completed", elapsed)

        st.success(f"✅ 回测完成！耗时 {elapsed:.1f} 秒 | 运行ID: #{run_id}")
        return results, run_id, benchmark_df

    except Exception as e:
        storage.update_run_status(run_id, "failed", time.time() - start_time)
        st.error(f"回测失败: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None, run_id, None


# ============================================================
# OTP 邮件验证（防止他人乱刷）
# ============================================================
_OTP_TTL = 300           # 验证码有效期（秒）
_OTP_MAX_ATTEMPTS = 5    # 最大尝试次数


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_otp_email(otp: str) -> bool:
    """通过 163 SMTP SSL 发送验证码到绑定邮箱，成功返回 True。"""
    try:
        cfg = st.secrets.get("smtp", {})
        host = str(cfg.get("host", "smtp.163.com"))
        port = int(cfg.get("port", 465))
        user = str(cfg.get("user", ""))
        password = str(cfg.get("password", ""))
        receiver = str(cfg.get("receiver", user))

        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = receiver
        msg["Subject"] = f"【回测系统】动态验证码：{otp}"
        body = (
            f"您好，\n\n"
            f"您的回测系统动态验证码为：\n\n"
            f"        {otp}\n\n"
            f"验证码有效期 5 分钟，请尽快输入。\n"
            f"如非本人操作，请忽略此邮件。\n"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            server.login(user, password)
            server.sendmail(user, receiver, msg.as_string())
        return True
    except Exception as e:
        st.error(f"邮件发送失败：{e}")
        return False


def _otp_gate() -> bool:
    """
    OTP 门控 UI。
    - 已验证 → 静默返回 True
    - 未验证 → 渲染验证 UI，返回 False（调用方应接着调用 st.stop()）
    """
    if st.session_state.get("_otp_verified"):
        return True

    st.markdown("---")
    st.subheader("🔐 运行回测需要身份验证")
    st.caption(
        "为防止他人滥用后台资源，每次会话首次运行回测需要通过邮件验证码确认身份。"
        "验证码将发送到绑定邮箱，**本次会话只需验证一次**（关闭标签页后重置）。"
    )

    expiry = st.session_state.get("_otp_expiry", 0.0)
    has_pending = expiry > time.time()

    col_btn, col_tip = st.columns([1, 3])
    with col_btn:
        label = "🔄 重新发送" if has_pending else "📧 发送验证码"
        if st.button(label, use_container_width=True, key="_otp_send_btn"):
            otp = _generate_otp()
            with st.spinner("正在发送邮件…"):
                if _send_otp_email(otp):
                    st.session_state["_otp_code"] = otp
                    st.session_state["_otp_expiry"] = time.time() + _OTP_TTL
                    st.session_state["_otp_attempts"] = 0
                    st.session_state.pop("_otp_input", None)
                    expiry = st.session_state["_otp_expiry"]
                    has_pending = True
                    st.success("✉️ 验证码已发送，请查收邮件！")
    with col_tip:
        if has_pending:
            remaining = max(0, int(expiry - time.time()))
            st.caption(f"⏱️ 验证码剩余有效期：{remaining // 60} 分 {remaining % 60:02d} 秒")

    if has_pending:
        attempts = st.session_state.get("_otp_attempts", 0)
        if attempts >= _OTP_MAX_ATTEMPTS:
            st.error("❌ 验证失败次数过多，请重新发送验证码。")
        else:
            entered = st.text_input(
                "请输入 6 位验证码", max_chars=6, placeholder="000000", key="_otp_input",
            )
            if st.button("✅ 验证并解锁回测", type="primary", key="_otp_verify_btn"):
                if time.time() > st.session_state.get("_otp_expiry", 0.0):
                    st.error("⚠️ 验证码已过期，请重新发送。")
                elif entered == st.session_state.get("_otp_code", "~~INVALID~~"):
                    st.session_state["_otp_verified"] = True
                    st.success("✅ 验证成功！页面即将刷新…")
                    st.rerun()
                else:
                    st.session_state["_otp_attempts"] = attempts + 1
                    left = _OTP_MAX_ATTEMPTS - attempts - 1
                    st.error(f"❌ 验证码错误，还有 {left} 次机会。")

    st.markdown("---")
    return False


# ---- OTP 门控：未验证时阻止后续执行 ----
if not _otp_gate():
    st.stop()

# ---- 手动选择模式：先看阶段一二，再选策略进行阶段三 ----
if _is_manual_phase3:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_phase12 = st.button("🚀 运行阶段一 & 二", type="primary", use_container_width=True)
    with col_btn2:
        btn_phase3 = st.button("⚡ 继续阶段三", use_container_width=True,
                                disabled=("_manual_candidates" not in st.session_state))

    # 候选策略选择器（仅在阶段一二完成后显示）
    if "_manual_candidates" in st.session_state:
        selected_strategy = st.selectbox(
            "选择要优化的策略",
            st.session_state["_manual_candidates"],
            help="从阶段一（单指标）和阶段二（组合策略）的结果中选择一个策略进行阶段三参数优化。",
        )
    else:
        selected_strategy = None

    if btn_phase12:
        # 只运行阶段一+二（phase3_override="__SKIP__" 表示跳过阶段三）
        ret = _run_and_save(phase3_override="__SKIP__")
        if ret[0] is not None:
            results = ret[0]
            # 构建候选策略列表
            candidates = []
            p1 = results.get("phase1_df", pd.DataFrame())
            p2 = results.get("phase2_df", pd.DataFrame())
            if not p1.empty:
                candidates += p1.head(15)["指标名称"].tolist()
            if not p2.empty:
                for _, r in p2.head(15).iterrows():
                    cname = r.get("指标组合", r.get("指标名称", ""))
                    logic = r.get("逻辑", "")
                    candidates.append(f"{cname} [{logic}]" if logic else cname)
            st.session_state["_manual_candidates"] = candidates
            st.session_state["_manual_run_id"] = ret[1]
            st.rerun()

    if btn_phase3 and selected_strategy:
        ret = _run_and_save(phase3_override=selected_strategy)
        if ret[0] is not None:
            results, run_id, benchmark_df = ret
            # 清理临时状态
            st.session_state.pop("_manual_candidates", None)
            st.session_state.pop("_manual_run_id", None)
            _show_backtest_results(results, benchmark_df)

else:
    # ---- 自动模式：一键完成全部三阶段 ----
    if st.button("🚀 开始回测", type="primary", use_container_width=True):
        ret = _run_and_save()
        if ret[0] is not None:
            results, run_id, benchmark_df = ret
            _show_backtest_results(results, benchmark_df)
