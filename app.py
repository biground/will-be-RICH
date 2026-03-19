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
