import ast
files = [
    "app.py",
    "pages/1_策略市场.py",
    "pages/2_策略报告.py",
    "pages/3_历史记录.py",
    "pages/4_专业模式.py",
    "ui_utils.py",
    "signal_interpreter.py",
    "strategy_templates.py",
    "metrics_translator.py",
]
for f in files:
    try:
        ast.parse(open(f, encoding="utf-8").read())
        print(f"OK: {f}")
    except SyntaxError as e:
        print(f"ERROR {f}: {e}")
print("done")
