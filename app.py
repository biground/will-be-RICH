"""
ETF回测可视化系统 — Streamlit 主入口
"""

import streamlit as st

st.set_page_config(
    page_title="ETF技术指标回测系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- 固定顶部导航栏 ----
_NAV_CSS = """
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
    <a href="/" target="_self" class="active">🏠 首页</a>
    <a href="/新建回测" target="_self">🚀 新建回测</a>
    <a href="/查看结果" target="_self">📊 查看结果</a>
    <a href="/历史记录" target="_self">📚 历史记录</a>
</div>
"""
st.markdown(_NAV_CSS, unsafe_allow_html=True)

# 主页
st.title("📈 ETF 技术指标回测系统")
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 🚀 新建回测
    自定义参数，运行三阶段回测流程
    - 选择目标 ETF
    - 设置回测周期
    - 自定义费率与资金
    """)
    st.page_link("pages/1_新建回测.py", label="开始回测 →", icon="🚀")
    st.caption("配置目标、周期、费率等参数，一键运行三阶段策略筛选流程")

with col2:
    st.markdown("""
    ### 📊 查看结果
    浏览单次回测的详细结果
    - 三阶段指标排名
    - 交互式图表
    - 交易记录明细
    """)
    st.page_link("pages/2_查看结果.py", label="查看结果 →", icon="📊")
    st.caption("查看单次回测的全部指标、图表与交易明细，支持导出 CSV")

with col3:
    st.markdown("""
    ### 📚 历史记录
    管理与对比多次回测
    - 查看所有运行记录
    - 跨策略对比
    - 删除历史数据
    """)
    st.page_link("pages/3_历史记录.py", label="历史记录 →", icon="📚")
    st.caption("管理所有历史回测，横向对比不同标的或参数下的最优策略表现")

st.markdown("---")
st.caption("基于 VectorBT + pandas-ta + AKShare 构建 | 数据来源: AKShare")
