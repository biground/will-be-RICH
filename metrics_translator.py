"""
指标翻译层 — 将专业量化指标翻译为散户能理解的语言

每个指标都会返回：通俗名称、格式化数值、好/中/差等级、
一句话解释、以及红绿灯颜色。
"""


# ------------------------------------------------------------------
# 单指标翻译
# ------------------------------------------------------------------
_METRIC_TRANSLATIONS = {
    "年化收益率": {
        "label": "每年大概赚多少",
        "unit": "%",
        "good": 10.0,
        "warn": 0.0,
        "higher_better": True,
        "explain": lambda v: (
            f"每年平均赚 {v:.1f}%，"
            + ("优于大部分银行理财" if v > 5 else "表现一般" if v > 0 else "亏钱了")
        ),
    },
    "最大回撤": {
        "label": "最坏时候亏多少",
        "unit": "%",
        "good": -15.0,
        "warn": -30.0,
        "higher_better": False,
        "explain": lambda v: (
            f"历史上最多从高点跌了 {abs(v):.1f}%"
        ),
    },
    "夏普比率": {
        "label": "风险收益性价比",
        "unit": "",
        "good": 1.0,
        "warn": 0.5,
        "higher_better": True,
        "explain": lambda v: (
            "每承担 1 份风险能赚 {:.2f} 份收益，".format(v)
            + ("很划算" if v > 1 else "还行" if v > 0.5 else "不太划算")
        ),
    },
    "胜率": {
        "label": "每 10 次能赢几次",
        "unit": "%",
        "good": 55.0,
        "warn": 45.0,
        "higher_better": True,
        "explain": lambda v: f"每 10 次交易大约赢 {v / 10:.1f} 次",
    },
    "盈亏比": {
        "label": "赢的倍数",
        "unit": "倍",
        "good": 2.0,
        "warn": 1.0,
        "higher_better": True,
        "explain": lambda v: f"每次赚钱平均是亏钱的 {v:.1f} 倍",
    },
    "交易次数": {
        "label": "交易频率",
        "unit": "次",
        "good": None,
        "warn": None,
        "higher_better": None,
        "explain": lambda v: f"回测期间共交易 {int(v)} 次",
    },
    "卡玛比率": {
        "label": "收益回撤比",
        "unit": "",
        "good": 1.0,
        "warn": 0.5,
        "higher_better": True,
        "explain": lambda v: (
            "收益÷回撤 = {:.2f}，".format(v)
            + ("优秀" if v > 1 else "及格" if v > 0.5 else "偏低")
        ),
    },
    "索提诺比率": {
        "label": "下行风险性价比",
        "unit": "",
        "good": 1.5,
        "warn": 0.5,
        "higher_better": True,
        "explain": lambda v: "只考虑亏损风险时的收益效率 {:.2f}".format(v),
    },
    "盈利因子": {
        "label": "赚亏总额比",
        "unit": "",
        "good": 2.0,
        "warn": 1.0,
        "higher_better": True,
        "explain": lambda v: (
            f"总盈利是总亏损的 {v:.1f} 倍，"
            + ("赚多亏少" if v > 1.5 else "基本持平" if v > 1 else "亏多赚少")
        ),
    },
    "年化波动率": {
        "label": "价格波动幅度",
        "unit": "%",
        "good": -20.0,
        "warn": -35.0,
        "higher_better": False,
        "explain": lambda v: f"年化波动 {abs(v):.1f}%，波动越小越稳定",
    },
    "VaR_95": {
        "label": "单日最大风险",
        "unit": "%",
        "good": -1.5,
        "warn": -3.0,
        "higher_better": False,
        "explain": lambda v: f"95% 的情况下单日最多跌 {abs(v):.2f}%",
    },
    "CVaR_95": {
        "label": "极端日亏损",
        "unit": "%",
        "good": -2.0,
        "warn": -4.0,
        "higher_better": False,
        "explain": lambda v: f"最差的 5% 交易日平均跌 {abs(v):.2f}%",
    },
}


def translate_metric(name: str, value: float) -> dict:
    """
    翻译单个指标。

    Returns
    -------
    dict:
        {
          "name":        原始名称,
          "label":       通俗名称,
          "value":       格式化后的字符串,
          "raw":         原始数值,
          "level":       "好" | "中" | "差" | "-",
          "explanation": 一句话解释,
          "color":       "#10B981" | "#F59E0B" | "#EF4444" | "#6B7280",
        }
    """
    spec = _METRIC_TRANSLATIONS.get(name)
    if spec is None:
        return {
            "name": name,
            "label": name,
            "value": f"{value:.2f}" if isinstance(value, float) else str(value),
            "raw": value,
            "level": "-",
            "explanation": "",
            "color": "#6B7280",
        }

    # 格式化
    unit = spec["unit"]
    if unit == "%":
        formatted = f"{value:.1f}%"
    elif unit == "倍":
        formatted = f"{value:.1f} 倍"
    elif unit == "次":
        formatted = f"{int(value)} 次"
    else:
        formatted = f"{value:.2f}"

    # 等级
    higher = spec["higher_better"]
    good_th = spec["good"]
    warn_th = spec["warn"]

    if higher is None or good_th is None:
        level = "-"
        color = "#6B7280"
    elif higher:
        if value >= good_th:
            level, color = "好", "#10B981"
        elif value >= warn_th:
            level, color = "中", "#F59E0B"
        else:
            level, color = "差", "#EF4444"
    else:
        # lower is better (回撤、波动率取绝对值后比)
        abs_val = -abs(value) if value > 0 else value  # 统一为负值
        if abs_val >= good_th:
            level, color = "好", "#10B981"
        elif abs_val >= warn_th:
            level, color = "中", "#F59E0B"
        else:
            level, color = "差", "#EF4444"

    explanation = spec["explain"](value)

    return {
        "name": name,
        "label": spec["label"],
        "value": formatted,
        "raw": value,
        "level": level,
        "explanation": explanation,
        "color": color,
    }


def translate_metrics(metrics: dict) -> dict[str, dict]:
    """批量翻译多个指标。返回 {原始名称: 翻译结果dict}"""
    return {k: translate_metric(k, v) for k, v in metrics.items() if isinstance(v, (int, float))}


# ------------------------------------------------------------------
# 策略等级一句话总结
# ------------------------------------------------------------------
_GRADE_MESSAGES = {
    "A": "这个策略表现 **优秀**，历史收益稳定、回撤可控，值得重点关注",
    "B": "这个策略表现 **良好**，整体盈利能力不错，风险在合理范围内",
    "C": "这个策略表现 **中等**，有一定盈利能力但波动较大，需要谨慎",
    "D": "这个策略表现 **偏弱**，风险收益比不太理想，建议搭配其他策略",
    "F": "这个策略 **不推荐**，历史表现较差，风险大于收益",
}


def get_strategy_grade_summary(grade: str, score: float, annual_return: float = 0, max_drawdown: float = 0) -> str:
    """
    根据策略等级返回面向散户的一句话总结。
    """
    base = _GRADE_MESSAGES.get(grade, "策略评估中")
    parts = [f"综合评分 **{score:.0f}** 分（**{grade}** 级）—— {base}。"]
    if annual_return != 0:
        parts.append(f"过去每年平均赚 **{annual_return:.1f}%**")
    if max_drawdown != 0:
        parts.append(f"最坏时临时亏过 **{abs(max_drawdown):.1f}%**")
    return "，".join(parts) + "。"


# ------------------------------------------------------------------
# 风险提示
# ------------------------------------------------------------------
def get_risk_warning(max_drawdown: float, init_cash: float = 100_000) -> str:
    """
    用具体金额来说明风险，让用户有直观感受。
    """
    loss_amount = init_cash * abs(max_drawdown) / 100
    return (
        f"⚠️ 使用这个策略，历史上最坏的情况是：你投入的 "
        f"**{init_cash / 10000:.0f} 万元**可能暂时亏损 "
        f"**{loss_amount / 10000:.2f} 万元**（{abs(max_drawdown):.1f}%），"
        f"通常需要几个月才能恢复。"
    )


# ------------------------------------------------------------------
# 大字号信号卡片 HTML
# ------------------------------------------------------------------
_ACTION_STYLE = {
    "买入": {"color": "#10B981", "bg": "#ECFDF5", "icon": "🟢"},
    "卖出": {"color": "#EF4444", "bg": "#FEF2F2", "icon": "🔴"},
    "观望": {"color": "#F59E0B", "bg": "#FFFBEB", "icon": "🟡"},
    "持有": {"color": "#6366F1", "bg": "#EEF2FF", "icon": "🔵"},
}


def signal_card_html(action: str, confidence: int, reason: str) -> str:
    """
    生成大号信号卡片的 HTML（用于首页展示）。
    """
    style = _ACTION_STYLE.get(action, _ACTION_STYLE["观望"])
    return f"""
<div style="background:{style['bg']};border:2px solid {style['color']};
     border-radius:16px;padding:1.8rem 2rem;text-align:center;margin:1rem 0;">
  <div style="font-size:1rem;color:#6B7280;margin-bottom:0.4rem;">当前建议</div>
  <div style="font-size:2.5rem;font-weight:800;color:{style['color']};
       margin-bottom:0.4rem;">
    {style['icon']}  {action}
  </div>
  <div style="font-size:0.9rem;color:#4B5563;margin-bottom:0.8rem;">{reason}</div>
  <div style="background:#E5E7EB;border-radius:99px;height:8px;margin:0 auto;max-width:300px;">
    <div style="background:{style['color']};height:8px;border-radius:99px;
         width:{confidence}%;"></div>
  </div>
  <div style="font-size:0.78rem;color:#9CA3AF;margin-top:0.3rem;">
    置信度 {confidence}%
  </div>
</div>
"""


def traffic_light_card_html(label: str, value: str, level: str, color: str, explanation: str = "") -> str:
    """
    红绿灯指标卡片 HTML（用于结果页核心三指标）。
    """
    icon_map = {"好": "🟢", "中": "🟡", "差": "🔴", "-": "⚪"}
    icon = icon_map.get(level, "⚪")
    return f"""
<div style="background:#fff;border:1.5px solid #E0E7FF;border-radius:12px;
     padding:1.2rem;text-align:center;box-shadow:0 1px 4px rgba(99,102,241,.07);">
  <div style="font-size:0.8rem;color:#6B7280;margin-bottom:0.3rem;">{label}</div>
  <div style="font-size:1.8rem;font-weight:700;color:{color};">{icon} {value}</div>
  <div style="font-size:0.75rem;color:#9CA3AF;margin-top:0.3rem;">{explanation}</div>
</div>
"""
