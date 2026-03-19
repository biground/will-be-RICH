"""
数据获取模块 — 通过 AKShare 获取ETF日线数据与基准指数数据，支持本地CSV缓存。
"""

import os
import pandas as pd
import akshare as ak

from config import (
    ETF_SYMBOL, BENCHMARK_SYMBOL,
    START_DATE, END_DATE,
    DATA_ADJUST, DATA_DIR,
)


def _ensure_cache_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _cache_path(symbol: str, suffix: str = "") -> str:
    fname = f"{symbol}_{START_DATE}_{END_DATE}{suffix}.csv"
    return os.path.join(DATA_DIR, fname)


def _clear_proxy():
    """清除代理环境变量并显式设置 NO_PROXY=* 让 requests 绕过所有代理"""
    saved = {}
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        saved[var] = os.environ.pop(var, "")  # 保存原值（空字符串=未设置）
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    return saved


def _restore_proxy(saved: dict):
    for var, val in saved.items():
        if val:
            os.environ[var] = val
        else:
            os.environ.pop(var, None)


def _standardize_etf(df: pd.DataFrame) -> pd.DataFrame:
    """将 AKShare ETF 数据标准化为 OHLCV 格式。"""
    col_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    # 保留所需列
    cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    return df[cols].astype(float)


def _standardize_index(df: pd.DataFrame) -> pd.DataFrame:
    """将 AKShare 指数数据标准化。"""
    col_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    return df[cols].astype(float)


def fetch_etf_data(
    symbol: str = ETF_SYMBOL,
    start: str = START_DATE,
    end: str = END_DATE,
    adjust: str = DATA_ADJUST,
) -> pd.DataFrame:
    """
    获取ETF日线数据。优先从本地缓存读取，否则从 AKShare 获取并缓存。

    Returns:
        DataFrame, index=DatetimeIndex, columns=[open, high, low, close, volume, amount]
    """
    _ensure_cache_dir()
    cache = _cache_path(symbol, f"_{adjust}")

    if os.path.exists(cache):
        print(f"[数据] 从缓存加载 {symbol} ...")
        df = pd.read_csv(cache, index_col="date", parse_dates=True)
        return df

    print(f"[数据] 从 AKShare 获取 {symbol} ({start} ~ {end}, {adjust}) ...")
    saved_proxy = _clear_proxy()
    try:
        raw = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust=adjust,
        )
    finally:
        _restore_proxy(saved_proxy)
    df = _standardize_etf(raw)
    df.to_csv(cache)
    print(f"[数据] 已缓存至 {cache}，共 {len(df)} 条记录")
    return df


def fetch_index_data(
    symbol: str = BENCHMARK_SYMBOL,
    start: str = START_DATE,
    end: str = END_DATE,
) -> pd.DataFrame:
    """
    获取指数日线数据作为基准。多种方式尝试。

    Returns:
        DataFrame, index=DatetimeIndex, columns=[open, high, low, close, volume, amount]
    """
    _ensure_cache_dir()
    cache = _cache_path(symbol, "_index")

    if os.path.exists(cache):
        print(f"[数据] 从缓存加载基准 {symbol} ...")
        df = pd.read_csv(cache, index_col="date", parse_dates=True)
        return df

    saved_proxy = _clear_proxy()
    try:
        # 方法1: index_zh_a_hist
        try:
            print(f"[数据] 方法1: index_zh_a_hist 获取 {symbol} ...")
            raw = ak.index_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
            )
            df = _standardize_index(raw)
            df.to_csv(cache)
            print(f"[数据] 已缓存至 {cache}，共 {len(df)} 条记录")
            return df
        except Exception as e1:
            print(f"[数据] 方法1失败: {e1}")

        # 方法2: stock_zh_index_daily_em
        try:
            print(f"[数据] 方法2: stock_zh_index_daily_em 获取 sh{symbol} ...")
            raw = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}")
            df = _standardize_index(raw)
            # 按日期筛选
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            df = df.loc[start_dt:end_dt]
            df.to_csv(cache)
            print(f"[数据] 已缓存至 {cache}，共 {len(df)} 条记录")
            return df
        except Exception as e2:
            print(f"[数据] 方法2失败: {e2}")
    finally:
        _restore_proxy(saved_proxy)

    # 方法3: 使用ETF数据作为基准近似
    print(f"[数据] 所有方法失败，使用ETF数据作为基准近似...")
    etf_cache = _cache_path(ETF_SYMBOL, f"_{DATA_ADJUST}")
    if os.path.exists(etf_cache):
        df = pd.read_csv(etf_cache, index_col="date", parse_dates=True)
        df.to_csv(cache)
        print(f"[数据] 已使用ETF数据作为基准替代，共 {len(df)} 条记录")
        return df

    raise RuntimeError(f"无法获取基准 {symbol} 数据，且ETF缓存不存在")


def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """一次性加载ETF数据和基准数据，返回 (etf_df, benchmark_df)。"""
    etf = fetch_etf_data()
    bench = fetch_index_data()
    # 对齐日期
    common_idx = etf.index.intersection(bench.index)
    return etf.loc[common_idx], bench.loc[common_idx]
