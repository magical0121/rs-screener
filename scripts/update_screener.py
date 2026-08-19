#!/usr/bin/env python3
"""
個人用 RS スクリーナー日次更新スクリプト

確定ロジック:
- Stage : Weinstein（米国株仕様・簡易版） SPYベンチマーク
- TT    : Minervini Trend Template 8条件（RyanJHamby）
          7〜8=強い / 5〜6=普通 / 4以下=弱い
          条件8: RS slope >= 0.15
- HQM   : 1M/3M/6M/1Y パーセンタイル平均
          いずれかが下位25%なら品質フィルター未通過扱い
- RS    : 簡易パーセンタイル（対ユニバース）

使い方:
  pip install -r requirements.txt
  python scripts/update_screener.py

出力:
  data/screener.json
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

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

# 拡大ユニバース（テーマ銘柄 + 主要成長/モメンタム候補）
DEFAULT_TICKERS = [
    # Mega / Core
    "AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN", "TSLA", "NFLX", "ORCL", "ADBE",
    # AI / Semi
    "NVDA", "AVGO", "AMD", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MU", "QCOM",
    "ARM", "SMCI", "AVAV", "MRVL", "SNPS", "CDNS", "INTC", "TXN", "ADI",
    # Cyber
    "CRWD", "PANW", "ZS", "FTNT", "OKTA", "NET", "S", "RPD", "CYBR", "TENB",
    # Cloud / Data / Software
    "SNOW", "DDOG", "MDB", "PLTR", "CRM", "NOW", "SHOP", "TEAM", "WDAY", "INTU",
    "HUBS", "VEEV", "TTD", "APP", "UBER", "ABNB",
    # Biotech / Health
    "REGN", "AMGN", "VRTX", "GILD", "BIIB", "MRNA", "LLY", "NVO", "ISRG", "DXCM",
    # Consumer / Other momentum names often watched
    "COST", "LLY", "CELH", "CAVA", "DUOL", "MELI", "SE", "NU", "SOFI", "HOOD",
    "COIN", "MSTR", "RBLX", "U", "PATH", "AI", "SOUN",
]

BENCHMARK = "SPY"


def load_themes() -> dict[str, list[str]]:
    if THEMES_PATH.exists():
        with open(THEMES_PATH, encoding="utf-8") as f:
            return json.load(f).get("themes", {})
    return {}


def download_history(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    # まとめて取得
    df = yf.download(
        tickers,
        period=period,
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    if len(tickers) == 1:
        t = tickers[0]
        if not df.empty:
            data[t] = df.dropna(how="all")
        return data

    for t in tickers:
        try:
            sub = df[t].dropna(how="all")
            if not sub.empty and "Close" in sub.columns:
                data[t] = sub
        except Exception:
            continue
    return data


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def calc_stage(close: pd.Series, bench_close: pd.Series) -> str:
    """簡易 Weinstein Stage（日足150SMA近似）"""
    if len(close) < 160 or len(bench_close) < 160:
        return "データ不足"

    c = close.iloc[-1]
    s150 = sma(close, 150)
    ma = s150.iloc[-1]
    # 傾き: 約50営業日（≈1ヶ月超）
    ma_prev = s150.iloc[-51] if len(s150.dropna()) > 50 else s150.dropna().iloc[0]
    slope = ((ma - ma_prev) / ma_prev) * 100 if ma_prev else 0

    # 簡易RS（価格/ベンチの相対）
    aligned = pd.concat([close, bench_close], axis=1, join="inner").dropna()
    if len(aligned) < 60:
        rs_ratio = 1.0
    else:
        rel = aligned.iloc[:, 0] / aligned.iloc[:, 1]
        rs_ratio = float(rel.iloc[-1] / rel.iloc[-60])

    dist = ((c - ma) / ma) * 100 if ma else 0

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
    """RyanJHamby系: 相対強度の傾き（約3ヶ月）"""
    aligned = pd.concat([close, bench], axis=1, join="inner").dropna()
    if len(aligned) < window + 5:
        return 0.0
    rel = (aligned.iloc[:, 0] / aligned.iloc[:, 1]).tail(window)
    x = np.arange(len(rel))
    # 正規化して傾きを取る
    y = rel.values / rel.values[0]
    coef = np.polyfit(x, y, 1)[0]
    # 日次傾きをスケール（経験的に ±0.3 付近）
    return float(coef * 100)


def calc_tt(close: pd.Series, high: pd.Series, low: pd.Series, bench: pd.Series) -> tuple[str, int]:
    """Minervini Trend Template 8条件 → 強い/普通/弱い"""
    if len(close) < 200:
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
        c > s150 and c > s200,          # 1
        s150 > s200,                    # 2
        s200 > s200_1m,                 # 3  約1ヶ月上昇
        s50 > s150 > s200,              # 4
        c > s50,                        # 5
        c >= low_52 * 1.30,             # 6
        c >= high_52 * 0.75,            # 7
        slope >= 0.15,                  # 8 RyanJHamby RS slope
    ]
    passed = sum(1 for x in conds if x)
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
    """各期間パーセンタイル→平均。下位25%が1つでもあればペナルティでFair以下寄りに。"""
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
            if math.isnan(v):
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
                score = min(score, 69.0)  # フィルター未通過は Good 未満に抑える
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
        # テーマスコア: RSとHQMの平均
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
    # 強い順
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def main() -> None:
    themes = load_themes()
    tickers = sorted(set(DEFAULT_TICKERS + [t for ms in themes.values() for t in ms]))
    all_syms = tickers + [BENCHMARK]

    print(f"Downloading {len(all_syms)} symbols...")
    hist = download_history(all_syms)
    if BENCHMARK not in hist:
        raise SystemExit("ベンチマーク SPY の取得に失敗しました")

    bench = hist[BENCHMARK]["Close"]
    returns_map: dict[str, dict[str, float]] = {}
    returns_3m: dict[str, float] = {}
    meta_rows = []

    for t in tickers:
        if t not in hist:
            print(f"  skip {t}: no data")
            continue
        df = hist[t]
        close = df["Close"]
        high = df["High"] if "High" in df.columns else close
        low = df["Low"] if "Low" in df.columns else close

        r1 = period_return(close, 21)
        r3 = period_return(close, 63)
        r6 = period_return(close, 126)
        r12 = period_return(close, 252)
        returns_map[t] = {"1m": r1, "3m": r3, "6m": r6, "1y": r12}
        returns_3m[t] = r3

        stage = calc_stage(close, bench)
        tt, tt_pass = calc_tt(close, high, low, bench)

        # 名前（取れなければティッカー）
        name = t
        try:
            info = yf.Ticker(t).info
            name = info.get("shortName") or info.get("longName") or t
        except Exception:
            pass

        industry = "—"
        try:
            industry = yf.Ticker(t).info.get("industry") or "—"
        except Exception:
            pass

        meta_rows.append(
            {
                "ticker": t,
                "name": name,
                "stage": stage,
                "tt": tt,
                "tt_pass": tt_pass,
                "industry": industry,
                "theme": theme_membership(t, themes),
            }
        )

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

    theme_scores = compute_theme_scores(stocks, themes)
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "themes": theme_scores,
        "stocks": sorted(stocks, key=lambda x: x["rs"], reverse=True),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} ({len(stocks)} stocks, {len(theme_scores)} themes)")


if __name__ == "__main__":
    main()
