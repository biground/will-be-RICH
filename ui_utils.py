"""
ui_utils.py — 全局 UI 工具函数与样式常量

蓝紫极简风格设计系统：
  - 主背景  #FAFAFF（近白淡紫）
  - 导航渐变 #4338CA → #7C3AED（蓝→紫）
  - 主强调色 #6366F1（Indigo）
  - 副背景  #F0EEFF（淡紫灰，侧边栏/卡片区）
  - 边框色  #E0E7FF
  - 文字主色 #1E1B4B（深靛蓝）
"""

import streamlit as st

# ============================================================
# 全局基础 CSS
# ============================================================
_BASE_CSS = """
<style>
/* ---- 整体背景与字体 ---- */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #FAFAFF;
    color: #1E1B4B;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

/* ---- 为固定导航条留出顶部空间 ---- */
[data-testid="stAppViewContainer"] > section > div:first-child {
    padding-top: 3.4rem !important;
}

/* ---- 侧边栏 ---- */
[data-testid="stSidebar"] {
    background-color: #F0EEFF !important;
    border-right: 1.5px solid #E0E7FF;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #4338CA;
    font-size: 0.9rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}

/* ---- Metric 卡片化 ---- */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1.5px solid #E0E7FF;
    border-radius: 10px;
    padding: 0.85rem 1rem 0.7rem;
    box-shadow: 0 1px 4px rgba(99, 102, 241, 0.07);
}
[data-testid="stMetricLabel"] {
    color: #6B7280;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
[data-testid="stMetricValue"] {
    color: #1E1B4B;
    font-size: 1.35rem;
    font-weight: 700;
}

/* ---- 导航栏 ---- */
.app-nav {
    position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
    background: linear-gradient(135deg, #4338CA 0%, #7C3AED 100%);
    display: flex; align-items: center;
    padding: 0 1.5rem;
    height: 3rem;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.25);
}
.app-nav .nav-brand {
    color: rgba(255,255,255,0.95);
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.02em;
    margin-right: auto;
    white-space: nowrap;
}
.app-nav .nav-links {
    display: flex; align-items: center; gap: 0;
}
.app-nav a {
    color: rgba(255,255,255,0.8);
    text-decoration: none;
    padding: 0 1.4rem;
    height: 3rem;
    display: flex; align-items: center;
    font-size: 0.88rem;
    font-weight: 500;
    transition: all 0.18s;
    border-bottom: 2.5px solid transparent;
    letter-spacing: 0.01em;
    white-space: nowrap;
}
.app-nav a:hover {
    color: #fff;
    background: rgba(255,255,255,0.1);
    border-bottom-color: rgba(255,255,255,0.5);
}
.app-nav a.active {
    color: #fff;
    background: rgba(255,255,255,0.12);
    border-bottom-color: #fff;
    font-weight: 600;
}

/* ---- 区块标题 ---- */
.section-hd {
    display: flex;
    align-items: baseline;
    gap: 0.7rem;
    padding-bottom: 0.5rem;
    border-bottom: 1.5px solid #E0E7FF;
    margin: 1.4rem 0 1rem;
}
.section-hd .bar {
    width: 4px; min-width: 4px;
    height: 1.3em;
    background: linear-gradient(180deg, #6366F1, #7C3AED);
    border-radius: 2px;
    align-self: stretch;
}
.section-hd .title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1E1B4B;
    margin: 0;
}
.section-hd .subtitle {
    font-size: 0.82rem;
    color: #6B7280;
    margin: 0;
}

/* ---- 首页 Hero ---- */
.hero {
    background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
    border-radius: 16px;
    padding: 2.5rem 3rem;
    margin: 1rem 0 2rem;
    border: 1.5px solid #E0E7FF;
}
.hero h1 {
    font-size: 2rem;
    font-weight: 800;
    color: #1E1B4B;
    margin: 0 0 0.5rem;
    letter-spacing: -0.02em;
}
.hero p {
    font-size: 1rem;
    color: #4B5563;
    margin: 0;
    line-height: 1.6;
    max-width: 640px;
}
.hero .badge {
    display: inline-block;
    background: #6366F1;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.18rem 0.65rem;
    border-radius: 99px;
    margin-right: 0.4rem;
    letter-spacing: 0.03em;
}

/* ---- 特性卡片 ---- */
.feat-card {
    background: #FFFFFF;
    border: 1.5px solid #E0E7FF;
    border-radius: 12px;
    padding: 1.5rem 1.5rem 1.2rem;
    height: 100%;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.07);
    position: relative;
    overflow: hidden;
    transition: box-shadow 0.2s, transform 0.2s;
}
.feat-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; bottom: 0;
    width: 4px;
    background: linear-gradient(180deg, #6366F1, #7C3AED);
    border-radius: 12px 0 0 12px;
}
.feat-card h3 {
    font-size: 1rem;
    font-weight: 700;
    color: #1E1B4B;
    margin: 0 0 0.6rem;
}
.feat-card p {
    font-size: 0.875rem;
    color: #4B5563;
    margin: 0 0 0.8rem;
    line-height: 1.55;
}
.feat-card ul {
    list-style: none;
    padding: 0; margin: 0 0 1.1rem;
}
.feat-card ul li {
    font-size: 0.82rem;
    color: #6B7280;
    padding: 0.18rem 0;
    padding-left: 1rem;
    position: relative;
}
.feat-card ul li::before {
    content: "–";
    position: absolute; left: 0;
    color: #6366F1;
    font-weight: 700;
}
.feat-card .card-link {
    display: inline-block;
    background: #6366F1;
    color: #fff !important;
    text-decoration: none;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.42rem 1.1rem;
    border-radius: 6px;
    letter-spacing: 0.02em;
    transition: background 0.18s;
}
.feat-card .card-link:hover {
    background: #4338CA;
}

/* ---- Footer ---- */
.app-footer {
    text-align: center;
    font-size: 0.78rem;
    color: #9CA3AF;
    padding: 1.5rem 0 0.5rem;
    border-top: 1px solid #E0E7FF;
    margin-top: 2.5rem;
}

/* ---- 隐藏默认 Streamlit 元素 ---- */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }

/* ---- Tab 样式优化 ---- */
[data-testid="stTabs"] [role="tab"] {
    font-size: 0.88rem;
    font-weight: 500;
    color: #6B7280;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #6366F1;
    border-bottom-color: #6366F1 !important;
}

/* ---- 按钮样式 ---- */
[data-testid="stBaseButton-primary"] {
    background-color: #6366F1 !important;
    border-color: #6366F1 !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #4338CA !important;
    border-color: #4338CA !important;
}

/* ---- Expander ---- */
[data-testid="stExpander"] summary {
    font-size: 0.9rem;
    color: #4338CA;
    font-weight: 500;
}

/* ---- Info / Warning / Success / Error 消息框 ---- */
[data-testid="stAlert"] {
    border-radius: 8px;
    border-left-width: 4px;
}

/* ---- 信号卡片 ---- */
.signal-card {
    background: #FFFFFF;
    border: 1.5px solid #E0E7FF;
    border-radius: 12px;
    padding: 0.9rem 1rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(99, 102, 241, 0.07);
    transition: box-shadow 0.2s;
}
.signal-card:hover {
    box-shadow: 0 3px 12px rgba(99, 102, 241, 0.15);
}
.signal-card .sig-name {
    font-size: 0.78rem;
    color: #6B7280;
    margin-bottom: 0.25rem;
}
.signal-card .sig-action {
    font-size: 1.1rem;
    font-weight: 700;
}

/* ---- 策略模板卡片 ---- */
.strategy-card {
    background: #FFFFFF;
    border: 1.5px solid #E0E7FF;
    border-radius: 14px;
    padding: 1.4rem 1.5rem 1.2rem;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.07);
    position: relative;
    overflow: hidden;
    transition: box-shadow 0.2s, transform 0.15s;
    height: 100%;
}
.strategy-card:hover {
    box-shadow: 0 4px 18px rgba(99, 102, 241, 0.18);
    transform: translateY(-2px);
}
.strategy-card .s-icon {
    font-size: 2rem;
    margin-bottom: 0.4rem;
}
.strategy-card .s-name {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1E1B4B;
    margin-bottom: 0.3rem;
}
.strategy-card .s-one-liner {
    font-size: 0.85rem;
    color: #4B5563;
    line-height: 1.5;
    margin-bottom: 0.6rem;
}
.strategy-card .s-tag {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 99px;
    color: #fff;
}
.strategy-card .s-detail {
    font-size: 0.8rem;
    color: #6B7280;
    line-height: 1.5;
    margin-top: 0.5rem;
}

/* ---- 市场状态横幅 ---- */
.market-banner {
    border-radius: 12px;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.market-banner .mb-icon {
    font-size: 2rem;
}
.market-banner .mb-text {
    flex: 1;
}
.market-banner .mb-state {
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 0.15rem;
}
.market-banner .mb-desc {
    font-size: 0.82rem;
    opacity: 0.85;
}
</style>
"""

# ============================================================
# 导航栏渲染
# ============================================================
_NAV_ITEMS = [
    ("home",     "/",        "今日信号"),
    ("backtest", "/新建回测", "新建回测"),
    ("results",  "/策略报告", "策略报告"),
    ("history",  "/历史记录", "历史记录"),
]

def render_nav(active_page: str) -> None:
    """
    注入全局 CSS 并渲染固定顶部导航栏。

    参数
    ----
    active_page : str
        当前页面的 key，取值 "home" / "backtest" / "results" / "history"
    """
    links_html = ""
    for key, href, label in _NAV_ITEMS:
        cls = ' class="active"' if key == active_page else ""
        links_html += f'<a href="{href}" target="_self"{cls}>{label}</a>\n'

    nav_html = f"""
{_BASE_CSS}
<div class="app-nav">
  <span class="nav-brand">RICH · ETF 择时助手</span>
  <nav class="nav-links">
    {links_html.strip()}
  </nav>
</div>
"""
    st.markdown(nav_html, unsafe_allow_html=True)


# ============================================================
# 区块标题
# ============================================================
def section_header(title: str, subtitle: str = "") -> str:
    """
    返回带左侧紫色竖条 + 下划线的区块标题 HTML。

    用法：
        st.markdown(section_header("单指标测试结果"), unsafe_allow_html=True)
    """
    sub_html = (
        f'<span class="subtitle">{subtitle}</span>'
        if subtitle else ""
    )
    return f"""
<div class="section-hd">
  <div class="bar"></div>
  <span class="title">{title}</span>
  {sub_html}
</div>
"""
