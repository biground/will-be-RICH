"""
结果持久化存储模块 — 使用 SQLite 保存回测结果、参数和历史记录
"""

import os
import json
import sqlite3
from datetime import datetime
from contextlib import contextmanager

import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time TEXT NOT NULL,
                etf_symbol TEXT NOT NULL,
                etf_name TEXT,
                benchmark_symbol TEXT,
                start_date TEXT,
                end_date TEXT,
                data_freq TEXT DEFAULT 'daily',
                init_cash REAL,
                entry_fees REAL,
                exit_fees REAL,
                status TEXT DEFAULT 'running',
                elapsed_seconds REAL,
                notes TEXT,
                extra_params_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phase1_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                indicator_name TEXT,
                total_return REAL,
                annual_return REAL,
                max_drawdown REAL,
                annual_vol REAL,
                sharpe REAL,
                calmar REAL,
                sortino REAL,
                win_rate REAL,
                profit_loss_ratio REAL,
                trade_count INTEGER,
                avg_hold_days REAL,
                annual_trade_freq REAL,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phase2_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                combo_name TEXT,
                logic TEXT,
                total_return REAL,
                annual_return REAL,
                max_drawdown REAL,
                annual_vol REAL,
                sharpe REAL,
                calmar REAL,
                sortino REAL,
                win_rate REAL,
                profit_loss_ratio REAL,
                trade_count INTEGER,
                avg_hold_days REAL,
                annual_trade_freq REAL,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phase3_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                strategy_name TEXT,
                param_json TEXT,
                total_return REAL,
                annual_return REAL,
                max_drawdown REAL,
                sharpe REAL,
                win_rate REAL,
                trade_count INTEGER,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS best_strategy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                strategy_name TEXT,
                annual_return REAL,
                sharpe REAL,
                max_drawdown REAL,
                win_rate REAL,
                trade_count INTEGER,
                core_metrics_json TEXT,
                aux_metrics_json TEXT,
                benchmark_metrics_json TEXT,
                monthly_returns_json TEXT,
                trade_log_json TEXT,
                equity_json TEXT,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            )
        """)
        # 兼容旧版数据库：添加 extra_params_json 列（重复执行时安全忽略）
        try:
            conn.execute("ALTER TABLE backtest_runs ADD COLUMN extra_params_json TEXT")
        except Exception:
            pass
        # 兼容旧版：添加 equity_json 列到 best_strategy（存储净值曲线）
        try:
            conn.execute("ALTER TABLE best_strategy ADD COLUMN equity_json TEXT")
        except Exception:
            pass


# ---- 写入操作 ----

def create_run(etf_symbol, etf_name, benchmark_symbol, start_date, end_date,
               data_freq, init_cash, entry_fees, exit_fees, notes="", extra_params=None):
    """创建一次新的回测运行记录，返回 run_id"""
    extra_json = json.dumps(extra_params or {}, ensure_ascii=False)
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO backtest_runs
                (run_time, etf_symbol, etf_name, benchmark_symbol, start_date, end_date,
                 data_freq, init_cash, entry_fees, exit_fees, status, notes, extra_params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)
        """, (
            datetime.now().isoformat(),
            etf_symbol, etf_name, benchmark_symbol,
            start_date, end_date, data_freq,
            init_cash, entry_fees, exit_fees, notes, extra_json,
        ))
        return cur.lastrowid


def update_run_status(run_id, status, elapsed_seconds=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE backtest_runs SET status=?, elapsed_seconds=? WHERE id=?",
            (status, elapsed_seconds, run_id),
        )


def save_phase1(run_id, metrics_list):
    """保存阶段一结果列表"""
    with get_conn() as conn:
        for m in metrics_list:
            conn.execute("""
                INSERT INTO phase1_results
                    (run_id, indicator_name, total_return, annual_return, max_drawdown,
                     annual_vol, sharpe, calmar, sortino, win_rate, profit_loss_ratio,
                     trade_count, avg_hold_days, annual_trade_freq)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, m.get("指标名称"),
                m.get("总收益率"), m.get("年化收益率"), m.get("最大回撤"),
                m.get("年化波动率"), m.get("夏普比率"), m.get("卡玛比率"),
                m.get("索提诺比率"), m.get("胜率"), m.get("盈亏比"),
                m.get("交易次数"), m.get("平均持仓天数"), m.get("年化交易频率"),
            ))


def save_phase2(run_id, combo_results):
    """保存阶段二结果"""
    with get_conn() as conn:
        for m in combo_results:
            conn.execute("""
                INSERT INTO phase2_results
                    (run_id, combo_name, logic, total_return, annual_return, max_drawdown,
                     annual_vol, sharpe, calmar, sortino, win_rate, profit_loss_ratio,
                     trade_count, avg_hold_days, annual_trade_freq)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                m.get("指标组合", m.get("指标名称")),
                m.get("逻辑", ""),
                m.get("总收益率"), m.get("年化收益率"), m.get("最大回撤"),
                m.get("年化波动率"), m.get("夏普比率"), m.get("卡玛比率"),
                m.get("索提诺比率"), m.get("胜率"), m.get("盈亏比"),
                m.get("交易次数"), m.get("平均持仓天数"), m.get("年化交易频率"),
            ))


def save_phase3(run_id, strategy_name, param_df):
    """保存阶段三参数优化结果"""
    if param_df is None or param_df.empty:
        return
    metric_cols = {"指标名称", "总收益率", "年化收益率", "最大回撤", "年化波动率",
                   "夏普比率", "卡玛比率", "索提诺比率", "胜率", "盈亏比",
                   "交易次数", "平均持仓天数", "年化交易频率"}
    param_cols = [c for c in param_df.columns if c not in metric_cols]

    with get_conn() as conn:
        for _, row in param_df.iterrows():
            params = {c: row[c] for c in param_cols if c in row.index}
            conn.execute("""
                INSERT INTO phase3_results
                    (run_id, strategy_name, param_json, total_return, annual_return,
                     max_drawdown, sharpe, win_rate, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, strategy_name, json.dumps(params),
                row.get("总收益率"), row.get("年化收益率"), row.get("最大回撤"),
                row.get("夏普比率"), row.get("胜率"), row.get("交易次数"),
            ))


def save_best_strategy(run_id, name, core, aux, bench, monthly_df, trade_log_df, equity_series=None):
    """保存最优策略详细信息"""
    monthly_json = monthly_df.to_json() if monthly_df is not None and not monthly_df.empty else "{}"
    trade_json = trade_log_df.to_json() if trade_log_df is not None and not trade_log_df.empty else "{}"
    equity_json = equity_series.to_json() if equity_series is not None else None
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO best_strategy
                (run_id, strategy_name, annual_return, sharpe, max_drawdown,
                 win_rate, trade_count, core_metrics_json, aux_metrics_json,
                 benchmark_metrics_json, monthly_returns_json, trade_log_json,
                 equity_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, name,
            core.get("年化收益率"), core.get("夏普比率"), core.get("最大回撤"),
            core.get("胜率"), core.get("交易次数"),
            json.dumps(core, ensure_ascii=False),
            json.dumps(aux, ensure_ascii=False),
            json.dumps(bench, ensure_ascii=False),
            monthly_json, trade_json, equity_json,
        ))


# ---- 读取操作 ----

def list_runs():
    """列出所有回测记录"""
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY id DESC"
            ).fetchall()
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return pd.DataFrame()


def get_run(run_id):
    """获取单次运行信息"""
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
            if row:
                d = dict(row)
                d["extra_params"] = json.loads(d.get("extra_params_json") or "{}")
                return d
            return None
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return None


def get_phase1(run_id):
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM phase1_results WHERE run_id=? ORDER BY sharpe DESC", (run_id,)
            ).fetchall()
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return pd.DataFrame()


def get_phase2(run_id):
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM phase2_results WHERE run_id=? ORDER BY sharpe DESC", (run_id,)
            ).fetchall()
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return pd.DataFrame()


def get_phase3(run_id):
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM phase3_results WHERE run_id=? ORDER BY sharpe DESC", (run_id,)
            ).fetchall()
            return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return pd.DataFrame()


def get_best_strategy(run_id):
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM best_strategy WHERE run_id=?", (run_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["core_metrics"] = json.loads(d.get("core_metrics_json", "{}"))
                d["aux_metrics"] = json.loads(d.get("aux_metrics_json", "{}"))
                d["benchmark_metrics"] = json.loads(d.get("benchmark_metrics_json", "{}"))
                return d
            return None
    except Exception as e:
        import warnings
        warnings.warn(f"数据库查询失败: {e}", stacklevel=2)
        return None


def delete_run(run_id):
    """删除一次运行记录及所有关联数据"""
    with get_conn() as conn:
        conn.execute("DELETE FROM phase1_results WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM phase2_results WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM phase3_results WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM best_strategy WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM backtest_runs WHERE id=?", (run_id,))


# 启动时自动初始化
init_db()
