#!/usr/bin/env python3
"""
個人用 RS スクリーナー日次更新スクリプト（全米株ユニバース）

対象:
- NASDAQ / NYSE / NYSE American 上場の普通株
- テスト銘柄・ワラント・単位・優先株っぽい記号は除外
- 最低価格・データ不足は計算後に除外

確定ロジック:
- Stage : Weinstein（米国株仕様・簡易版） SPYベンチマーク
- TT    : Minervini Trend Template 8条件（RyanJHamby）
- HQM   : 1M/3M/6M/1Y パーセンタイル平均
- RS    : ユニバース内パーセンタイル（3M）
"""

from __future__ import annotations

import io
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError as e:
    raise SystemExit("yfinance が必要です: pip install yfinance") from e

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
THEMES_PATH = DATA_DIR / "themes.json"
OUT_PATH = DATA_DIR / "screener.json"

BENCHMARK = "SPY"

# スクリーナー品質フィルター
MIN_PRICE = 5.0
MIN_HISTORY_DAYS = 200
BATCH_SIZE = 150  # yfinance 負荷対策

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"


def load_themes() -> dict[str, list[str]]:
    if THEMES_PATH.exists():
        with open(THEMES_PATH, encoding="utf-8") as f:
            return json.load(f).get("themes", {})
    return {}


def _fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 rs-screener"})
    with urlopen(req, timeout=60) as res:
        return res.read().decode("latin-1", errors="ignore")


def _clean_symbol(sym: str) -> str | None:
    if not sym:
        return None
    s = sym.strip().upper()
    # 特殊記号・テスト・ワラント等を除外
    if not re.fullmatch(r"[A-Z]{1,5}", s):
        return None
    if s.endswith("W") and len(s) >= 5:  # 粗いワラント除外
        return None
    return s


def fetch_us_tickers() -> list[str]:
    """NASDAQ + NYSE/AMEX の普通株ティッカーを取得"""
    tickers: set[str] = set()

    # NASDAQ
    try:
        text = _fetch_text(NASDAQ_URL)
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("File Creation")]
        if lines:
            header = lines[0].split("|")
            # Symbol|...|Test Issue|...|ETF|...
            for ln in lines[1:]:
                parts = ln.split("|")
                if len(parts) < 7:
                    continue
                sym = parts[0].strip()
                test = parts[3].strip().upper() if len(parts) > 3 else "N"
                etf = parts[6].strip().upper() if len(parts) > 6 else "N"
                if test == "Y" or etf == "Y":
                    continue
                name = parts[1] if len(parts) > 1 else ""
                if any(x in name.upper() for x in ["WARRANT", " UNIT", " RIGHT", "PREFERRED"]):
                    continue
                cleaned = _clean_symbol(sym)
                if cleaned:
                    tickers.add(cleaned)
    except Exception as e:
        print(f"NASDAQ list fetch failed: {e}")

    # NYSE / NYSE American など
    try:
        text = _fetch_text(OTHER_URL)
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("File Creation")]
        if lines:
            for ln in lines[1:]:
                parts = ln.split("|")
                if len(parts) < 7:
                    continue
                # ACT Symbol|...|Exchange|...|ETF|...|Test Issue
                sym = parts[0].strip()
                exchange = parts[2].strip().upper() if len(parts) > 2 else ""
                etf = parts[4].strip().upper() if len(parts) > 4 else "N"
                test = parts[6].strip().upper() if len(parts) > 6 else "N"
                if test == "Y" or etf == "Y":
                    continue
                # N=NYSE, A=NYSE American, P=NYSE Arca など。OTC系は除外気味に
                if exchange not in {"N", "A", "P", "Z", "Q"}:
                    # Q は他リスト側のNASDAQ表記のことがある
                    if exchange not in {"N", "A", "P"}:
                        continue
                name = parts[1] if len(parts) > 1 else ""
                if any(x in name.upper() for x in ["WARRANT", " UNIT", " RIGHT", "PREFERRED"]):
                    continue
                cleaned = _clean_symbol(sym)
                if cleaned:
                    tickers.add(cleaned)
    except Exception as e:
        print(f"OTHER list fetch failed: {e}")

    out = sorted(tickers)
    print(f"US ticker universe size: {len(out)}")
    return out


def download_history_batch(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    if not tickers:
        return data
    try:
        df = yf.download(
            tickers,
            period=period,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"download error: {e}")
        return data

    if len(tickers) == 1:
        t = tickers[0]
        if isinstance(df, pd.DataFrame) and not df.empty:
            data[t] = df.dropna(how="all")
        return data

    for t in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if t not in df.columns.get_level_values(0):
                    continue
                sub = df[t].dropna(how="all")
            else:
                sub = df.dropna(how="all")
            if not sub.empty and "Close" in sub.columns:
                data[t] = sub
        except Exception:
            continue
    return data


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def calc_stage(close: pd.Series, bench_close: pd.Series) -> str:
    if len(close) < 160 or len(bench_close) < 160:
        return "データ不足"

    c = float(close.iloc[-1])
    s150 = sma(close, 150)
    ma = float(s150.iloc[-1])
    ma_prev = float(s150.iloc[-51]) if len(s150.dropna()) > 50 else float(s150.dropna().iloc[0])
    slope = ((ma - ma_prev) / ma_prev) * 100 if ma_prev else 0.0

    aligned = pd.concat([close, bench_close], axis=1, join="inner").dropna()
    if len(aligned) < 60:
        rs_ratio = 1.0
    else:
        rel = aligned.iloc[:, 0] / aligned.iloc[:, 1]
        rs_ratio = float(rel.iloc[-1] / rel.iloc[-60])

    dist = ((c - ma) / ma) * 100 if ma else 0.0

    if c > ma and slope > 0.3 and rs_ratio >= 1.0:
        arrow = "↑" if slope > 1.0 else "→"
        return f"Stage2 {arrow}"
    if c < ma and slope < -0.3 and rs_ratio <= 1.0:
        return "Stage4 ↓"
    if abs(slope) < 0.8 and abs(dist) <= 8:
        return "Stage1 →"
    if c > ma and slope < 0:
        return "Stage3 →"
    if c > ma:
        return "Stage2 →"
    return "Stage4 ↓"


def rs_slope_vs_bench(close: pd.Series, bench: pd.Series, window: int = 63) -> float:
    aligned = pd.concat([close, bench], axis=1, join="inner").dropna()
    if len(aligned) < window + 5:
        return 0.0
    rel = (aligned.iloc[:, 0] / aligned.iloc[:, 1]).tail(window)
    x = np.arange(len(rel))
    y = rel.values / rel.values[0]
    coef = np.polyfit(x, y, 1)[0]
    return float(coef * 100)


def calc_tt(close: pd.Series, high: pd.Series, low: pd.Series, bench: pd.Series) -> tuple[str, int]:
    if len(close) < MIN_HISTORY_DAYS:
        return "弱い", 0

    c = float(close.iloc[-1])
    s50 = float(sma(close, 50).iloc[-1])
    s150 = float(sma(close, 150).iloc[-1])
    s200 = float(sma(close, 200).iloc[-1])
    s200_1m = float(sma(close, 200).iloc[-22]) if len(close) >= 222 else s200

    low_52 = float(low.tail(252).min())
    high_52 = float(high.tail(252).max())
    slope = rs_slope_vs_bench(close, bench)

    conds = [
        c > s150 and c > s200,
        s150 > s200,
        s200 > s200_1m,
        s50 > s150 > s200,
        c > s50,
        c >= low_52 * 1.30,
        c >= high_52 * 0.75,
        slope >= 0.15,
    ]
    passed = sum(1 for x in conds if bool(x))
    if passed >= 7:
        return "強い", passed
    if passed >= 5:
        return "普通", passed
    return "弱い", passed


def period_return(close: pd.Series, days: int) -> float:
    if len(close) <= days:
        return float("nan")
    a = float(close.iloc[-1])
    b = float(close.iloc[-days - 1])
    if b == 0:
        return float("nan")
    return (a / b - 1.0) * 100.0


def calc_hqm_scores(returns_map: dict[str, dict[str, float]]) -> dict[str, float]:
    periods = ["1m", "3m", "6m", "1y"]
    tickers = list(returns_map.keys())
    pcts: dict[str, list[float]] = {t: [] for t in tickers}
    quality_ok: dict[str, bool] = {t: True for t in tickers}

    for p in periods:
        vals = {t: returns_map[t].get(p, float("nan")) for t in tickers}
        series = pd.Series(vals)
        valid = series.dropna()
        if valid.empty:
            for t in tickers:
                pcts[t].append(float("nan"))
            continue
        for t in tickers:
            v = series[t]
            if isinstance(v, float) and math.isnan(v):
                pcts[t].append(float("nan"))
                quality_ok[t] = False
            else:
                rank = float((valid <= v).mean() * 100)
                pcts[t].append(rank)
                if rank < 25:
                    quality_ok[t] = False

    out: dict[str, float] = {}
    for t in tickers:
        arr = [x for x in pcts[t] if not math.isnan(x)]
        if not arr:
            out[t] = 0.0
        else:
            score = float(np.mean(arr))
            if not quality_ok[t]:
                score = min(score, 69.0)
            out[t] = round(score, 1)
    return out


def calc_rs_percentile(returns_3m: dict[str, float]) -> dict[str, int]:
    series = pd.Series(returns_3m).dropna()
    if series.empty:
        return {t: 50 for t in returns_3m}
    out = {}
    for t, v in returns_3m.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[t] = 50
        else:
            out[t] = int(round(float((series <= v).mean() * 100)))
    return out


def theme_membership(ticker: str, themes: dict[str, list[str]]) -> str:
    for name, members in themes.items():
        if ticker in members:
            return name
    return "—"


def compute_theme_scores(stocks: list[dict], themes: dict[str, list[str]]) -> list[dict]:
    result = []
    for name, members in themes.items():
        rows = [s for s in stocks if s["ticker"] in members]
        if not rows:
            result.append({"name": name, "score": 0, "label": "弱い", "leaders": []})
            continue
        score = int(round(np.mean([0.6 * s["rs"] + 0.4 * s["hqm"] for s in rows])))
        if score >= 80:
            label = "強い"
        elif score >= 55:
            label = "普通"
        else:
            label = "弱い"
        leaders = [
            s["ticker"]
            for s in sorted(rows, key=lambda x: (x["rs"], x["hqm"]), reverse=True)[:3]
            if s["rs"] >= 60
        ]
        result.append({"name": name, "score": score, "label": label, "leaders": leaders})
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def main() -> None:
    themes = load_themes()
    universe = fetch_us_tickers()
    if not universe:
        raise SystemExit("ティッカーリストの取得に失敗しました")

    # ベンチマーク + 全銘柄
    print("Downloading SPY...")
    bench_hist = download_history_batch([BENCHMARK], period="2y")
    if BENCHMARK not in bench_hist:
        raise SystemExit("ベンチマーク SPY の取得に失敗しました")
    bench = bench_hist[BENCHMARK]["Close"]

    returns_map: dict[str, dict[str, float]] = {}
    returns_3m: dict[str, float] = {}
    meta_rows: list[dict] = []

    total = len(universe)
    for i in range(0, total, BATCH_SIZE):
        batch = universe[i : i + BATCH_SIZE]
        print(f"Batch {i // BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1) // BATCH_SIZE}: {len(batch)} symbols")
        hist = download_history_batch(batch, period="2y")
        for t, df in hist.items():
            close = df["Close"].dropna()
            if len(close) < MIN_HISTORY_DAYS:
                continue
            price = float(close.iloc[-1])
            if price < MIN_PRICE:
                continue
            high = df["High"] if "High" in df.columns else close
            low = df["Low"] if "Low" in df.columns else close

            r1 = period_return(close, 21)
            r3 = period_return(close, 63)
            r6 = period_return(close, 126)
            r12 = period_return(close, 252)
            returns_map[t] = {"1m": r1, "3m": r3, "6m": r6, "1y": r12}
            returns_3m[t] = r3

            stage = calc_stage(close, bench)
            tt, _tt_pass = calc_tt(close, high, low, bench)

            meta_rows.append(
                {
                    "ticker": t,
                    "name": t,  # 全銘柄のinfo取得は遅いのでティッカー表示
                    "stage": stage,
                    "tt": tt,
                    "industry": "—",
                    "theme": theme_membership(t, themes),
                }
            )
        # レート制限対策
        time.sleep(1.0)

    print(f"Qualified symbols: {len(meta_rows)}")
    hqm_map = calc_hqm_scores(returns_map)
    rs_map = calc_rs_percentile(returns_3m)

    stocks = []
    for m in meta_rows:
        t = m["ticker"]
        stocks.append(
            {
                "ticker": t,
                "name": m["name"],
                "rs": rs_map.get(t, 50),
                "stage": m["stage"],
                "industry": m["industry"],
                "theme": m["theme"],
                "tt": m["tt"],
                "hqm": hqm_map.get(t, 0.0),
            }
        )

    # 表示用に上位を多めに残す（サイト負荷対策）。全件はJSONに入れる
    stocks_sorted = sorted(stocks, key=lambda x: x["rs"], reverse=True)
    theme_scores = compute_theme_scores(stocks_sorted, themes)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "universe_size": len(universe),
        "qualified_size": len(stocks_sorted),
        "themes": theme_scores,
        "stocks": stocks_sorted,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} (universe={len(universe)}, qualified={len(stocks_sorted)})")


if __name__ == "__main__":
    main()
