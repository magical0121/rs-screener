#!/usr/bin/env python3
"""
Stage2 背景入り 専用スクリーナー（日次更新）

判定（インジ Lookahead ON / フィルターOFF 相当）:
  1. 週足終値 > 直近12週の高値レンジ（現在週を除く）
  2. 週足終値 > 30週SMA
  → Stage2 条件
  → 前週は条件未達 & 今週達成 = Stage2 入り（Entry）

ユニバース:
  株価 >= $0.75
  20日平均出来高 >= 500,000
  売買代金（価格×20日平均出来高） >= $1,000,000

残す情報: RS / 業種 / 業種スコア / 業種強度
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError as e:
    raise SystemExit("yfinance が必要です: pip install yfinance") from e

try:
    yf.set_tz_cache_location("/tmp/yf_tz_cache")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "screener.json"
INDUSTRY_CACHE_PATH = DATA_DIR / "industry_cache.json"
THEMES_PATH = DATA_DIR / "themes.json"

BENCHMARK = "SPY"

MIN_PRICE = 0.75
MIN_AVG_VOL = 500_000
MIN_DOLLAR_VOL = 1_000_000
MIN_HISTORY_DAYS = 220
BATCH_SIZE = 120
RANGE_LEN = 12  # 週
SMA_LEN = 30    # 週

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

_US_EXCHANGES = {
    "NMS", "NYQ", "ASE", "NCM", "NGM", "NASDAQ", "NYSE", "AMEX", "BATS", "ARCA",
}


# ──────────────────────────────
# ユーティリティ
# ──────────────────────────────
def _http_get(url: str, timeout: int = 25) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def _naive_index(s: pd.Series) -> pd.Series:
    s = s.dropna().sort_index().copy()
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_convert("UTC").tz_localize(None)
    return s


# ──────────────────────────────
# ユニバース
# ──────────────────────────────
def _clean_symbol(sym: str) -> str | None:
    if not sym:
        return None
    s = sym.strip().upper()
    if not s or s.startswith("$"):
        return None
    # ワラント・単位・優先株っぽい記号を除外
    if re.search(r"[\^/]", s):
        return None
    if s.endswith(("W", "U", "R")) and len(s) <= 5:
        # 単純すぎる除外はしない（実在ティッカーもある）
        pass
    if "." in s or " " in s:
        return None
    if not re.match(r"^[A-Z]{1,5}$", s):
        return None
    return s


def fetch_us_tickers() -> list[str]:
    out: set[str] = set()
    for url in (NASDAQ_URL, OTHER_URL):
        try:
            text = _http_get(url)
        except Exception as e:
            print(f"ticker list fail {url}: {e}")
            continue
        for line in text.splitlines():
            if not line or line.startswith("Symbol") or line.startswith("ACT Symbol") or line.startswith("File"):
                continue
            parts = line.split("|")
            if not parts:
                continue
            sym = _clean_symbol(parts[0])
            if not sym:
                continue
            # テスト銘柄など
            test_flag = parts[-1].strip().upper() if len(parts) > 1 else ""
            if "Y" == test_flag or test_flag.startswith("Y"):
                # nasdaqlisted の Test Issue 列が Y
                if "nasdaqlisted" in url and len(parts) >= 7 and parts[3].strip().upper() == "Y":
                    continue
            out.add(sym)
    tickers = sorted(out)
    print(f"US ticker universe size: {len(tickers)}")
    return tickers


# ──────────────────────────────
# 業種
# ──────────────────────────────
def load_industry_cache() -> dict[str, dict[str, str]]:
    if INDUSTRY_CACHE_PATH.exists():
        try:
            with open(INDUSTRY_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_industry_cache(cache: dict[str, dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDUSTRY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_industry_map() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    try:
        import financedatabase as fd

        eq = fd.Equities()
        df = eq.select(country="United States")
        if df is None or df.empty:
            return out
        if "exchange" in df.columns:
            mask = df["exchange"].astype(str).str.upper().isin(_US_EXCHANGES)
            df = df[mask | df["exchange"].isna()]
        for sym, row in df.iterrows():
            ticker = str(sym).strip().upper()
            if not ticker or not re.match(r"^[A-Z]{1,5}$", ticker):
                continue
            industry = str(row.get("industry") or "").strip()
            sector = str(row.get("sector") or "").strip()
            name = str(row.get("name") or ticker).strip()
            if industry or sector:
                out[ticker] = {
                    "industry": industry or "—",
                    "sector": sector or "—",
                    "name": name or ticker,
                }
    except Exception as e:
        print(f"financedatabase industry fail: {e}")
    print(f"industry map size: {len(out)}")
    return out


def apply_industry_cache(meta_rows: list[dict], cache: dict[str, dict[str, str]]) -> None:
    for m in meta_rows:
        t = m["ticker"]
        if t in cache:
            c = cache[t]
            if not m.get("industry") or m["industry"] in ("", "—"):
                m["industry"] = c.get("industry") or "—"
            if not m.get("sector") or m["sector"] in ("", "—"):
                m["sector"] = c.get("sector") or "—"
            if (not m.get("name") or m["name"] == t) and c.get("name"):
                m["name"] = c["name"]


# ──────────────────────────────
# 価格取得
# ──────────────────────────────
def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    cols = {str(c).lower(): c for c in df.columns}
    need = {}
    for k in ("open", "high", "low", "close", "volume"):
        if k not in cols:
            return None
        need[k.capitalize() if k != "volume" else "Volume"] = df[cols[k]]
    out = pd.DataFrame(need).dropna()
    if out.empty:
        return None
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None)
    return out


def download_history_batch(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    if not tickers:
        return result
    try:
        data = yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"download batch fail: {e}")
        return result

    if data is None or data.empty:
        return result

    if len(tickers) == 1:
        t = tickers[0]
        norm = _normalize_ohlcv(data)
        if norm is not None and len(norm) >= MIN_HISTORY_DAYS:
            result[t] = norm
        return result

    for t in tickers:
        try:
            if t not in data.columns.get_level_values(0):
                continue
            sub = data[t].copy()
            norm = _normalize_ohlcv(sub)
            if norm is not None and len(norm) >= MIN_HISTORY_DAYS:
                result[t] = norm
        except Exception:
            continue
    return result


# ──────────────────────────────
# Stage2 判定（Lookahead ON 相当）
# ──────────────────────────────
def calc_stage2_entry(close: pd.Series, high: pd.Series) -> dict:
    """
    Lookahead ON 相当:
      日足を週足(W-FRI)にリサンプルし、今週の未確定バーも含める
    条件:
      breakout = 週足終値 > 過去 RANGE_LEN 週の終値高値
      above    = 週足終値 > 30週SMA
    Entry:
      今週条件達成 & 前週は未達成
    """
    out = {
        "stage2_active": False,
        "stage2_entry": False,
        "breakout_pct": None,
        "pct_from_30w": None,
        "range_high": None,
        "sma30": None,
    }
    try:
        close = _naive_index(close)
        high = _naive_index(high.reindex(close.index).ffill())
        w = (
            pd.DataFrame({"c": close, "h": high})
            .resample("W-FRI")
            .agg({"c": "last", "h": "max"})
            .dropna()
        )
        if len(w) < SMA_LEN + RANGE_LEN + 2:
            return out

        w["sma30"] = w["c"].rolling(SMA_LEN, min_periods=SMA_LEN).mean()
        # 過去RANGE_LEN週（現在週除外）の終値高値
        w["range_high"] = w["c"].shift(1).rolling(RANGE_LEN, min_periods=max(5, RANGE_LEN // 2)).max()
        w["breakout"] = w["c"] > w["range_high"]
        w["above"] = w["c"] > w["sma30"]
        w["stage2"] = w["breakout"].fillna(False) & w["above"].fillna(False)

        last = w.iloc[-1]
        prev = w.iloc[-2]
        active = bool(last["stage2"])
        entry = bool(last["stage2"]) and (not bool(prev["stage2"]))

        last_c = float(last["c"])
        last_sma = float(last["sma30"]) if not pd.isna(last["sma30"]) else None
        rh = float(last["range_high"]) if not pd.isna(last["range_high"]) else None

        out["stage2_active"] = active
        out["stage2_entry"] = entry
        out["sma30"] = last_sma
        out["range_high"] = rh
        if rh and rh > 0:
            out["breakout_pct"] = round((last_c / rh - 1.0) * 100.0, 2)
        if last_sma and last_sma > 0:
            out["pct_from_30w"] = round((last_c / last_sma - 1.0) * 100.0, 2)
        return out
    except Exception:
        return out


def period_return(close: pd.Series, days: int) -> float:
    c = close.dropna()
    if len(c) < days + 2:
        return float("nan")
    a = float(c.iloc[-1])
    b = float(c.iloc[-days - 1])
    if b == 0:
        return float("nan")
    return (a / b - 1.0) * 100.0


def calc_rs_percentile(returns_3m: dict[str, float]) -> dict[str, int]:
    items = [(k, v) for k, v in returns_3m.items() if v is not None and not math_isnan(v)]
    if not items:
        return {}
    items.sort(key=lambda x: x[1])
    n = len(items)
    out: dict[str, int] = {}
    for i, (k, _) in enumerate(items):
        out[k] = int(round((i + 1) / n * 100))
    return out


def math_isnan(x: float) -> bool:
    try:
        return x != x
    except Exception:
        return True


def compute_industry_scores(stocks: list[dict], min_count: int = 3) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for s in stocks:
        ind = s.get("industry") or "—"
        buckets.setdefault(ind, []).append(s)

    rows = []
    for name, items in buckets.items():
        if name in ("", "—") or len(items) < min_count:
            continue
        rs_vals = [float(x.get("rs") or 0) for x in items]
        score = int(round(float(np.mean(rs_vals))))
        if score >= 70:
            label = "強い"
        elif score >= 50:
            label = "普通"
        else:
            label = "弱い"
        leaders = [
            x["ticker"]
            for x in sorted(items, key=lambda z: z.get("rs") or 0, reverse=True)[:3]
        ]
        rows.append(
            {
                "name": name,
                "score": score,
                "label": label,
                "leaders": leaders,
                "count": len(items),
            }
        )
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


# ──────────────────────────────
# main
# ──────────────────────────────
def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    universe = fetch_us_tickers()
    if not universe:
        raise SystemExit("ticker universe empty")

    industry_map = fetch_industry_map()
    cache = load_industry_cache()
    # cache に industry_map を反映
    for t, info in industry_map.items():
        cache[t] = {
            "industry": info.get("industry") or "—",
            "sector": info.get("sector") or "—",
            "name": info.get("name") or t,
        }

    # ベンチマーク
    bench_hist = download_history_batch([BENCHMARK], period="2y")
    if BENCHMARK not in bench_hist:
        raise SystemExit("SPY download failed")
    bench_close = bench_hist[BENCHMARK]["Close"]

    meta_rows: list[dict] = []
    returns_3m: dict[str, float] = {}

    total = len(universe)
    for i in range(0, total, BATCH_SIZE):
        batch = universe[i : i + BATCH_SIZE]
        print(f"batch {i // BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)})")
        hist = download_history_batch(batch, period="2y")
        for t, df in hist.items():
            try:
                close = df["Close"]
                high = df["High"]
                vol = df["Volume"]
                price = float(close.iloc[-1])
                if price < MIN_PRICE:
                    continue
                avg_vol = float(vol.tail(20).mean())
                if avg_vol < MIN_AVG_VOL:
                    continue
                dollar_vol = price * avg_vol
                if dollar_vol < MIN_DOLLAR_VOL:
                    continue

                st = calc_stage2_entry(close, high)
                # Entry または Active を候補に（表示は Entry 優先）
                if not (st["stage2_entry"] or st["stage2_active"]):
                    continue

                r3 = period_return(close, 63)
                returns_3m[t] = r3

                info = cache.get(t) or industry_map.get(t) or {}
                meta_rows.append(
                    {
                        "ticker": t,
                        "name": info.get("name") or t,
                        "industry": info.get("industry") or "—",
                        "sector": info.get("sector") or "—",
                        "price": round(price, 4),
                        "avg_vol": int(avg_vol),
                        "dollar_vol": int(dollar_vol),
                        "stage2_entry": bool(st["stage2_entry"]),
                        "stage2_active": bool(st["stage2_active"]),
                        "breakout_pct": st.get("breakout_pct"),
                        "pct_from_30w": st.get("pct_from_30w"),
                    }
                )
            except Exception as e:
                print(f"fail {t}: {e}")
                continue
        time.sleep(0.8)

    apply_industry_cache(meta_rows, cache)
    save_industry_cache(cache)

    rs_map = calc_rs_percentile(returns_3m)

    stocks = []
    for m in meta_rows:
        t = m["ticker"]
        stocks.append(
            {
                "ticker": t,
                "name": m["name"],
                "rs": rs_map.get(t, 50),
                "industry": m["industry"],
                "sector": m.get("sector") or "—",
                "price": m["price"],
                "stage2_entry": m["stage2_entry"],
                "stage2_active": m["stage2_active"],
                "breakout_pct": m.get("breakout_pct"),
                "pct_from_30w": m.get("pct_from_30w"),
                "status": "Entry" if m["stage2_entry"] else "Active",
            }
        )

    # Entry を上に、その中で RS 順
    stocks_sorted = sorted(
        stocks,
        key=lambda x: (0 if x["stage2_entry"] else 1, -(x.get("rs") or 0)),
    )

    industry_scores = compute_industry_scores(stocks_sorted)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "universe_size": len(universe),
        "qualified_size": len(stocks_sorted),
        "entry_count": sum(1 for s in stocks_sorted if s["stage2_entry"]),
        "active_count": sum(1 for s in stocks_sorted if s["stage2_active"]),
        "logic": "Stage2 Entry = 12w high break + above 30w SMA (lookahead-on weekly)",
        "filters": {
            "min_price": MIN_PRICE,
            "min_avg_vol": MIN_AVG_VOL,
            "min_dollar_vol": MIN_DOLLAR_VOL,
            "range_len_weeks": RANGE_LEN,
            "sma_weeks": SMA_LEN,
        },
        "industries": industry_scores,
        "stocks": stocks_sorted,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f"Wrote {OUT_PATH} (universe={len(universe)}, "
        f"entry={payload['entry_count']}, active={payload['active_count']})"
    )


if __name__ == "__main__":
    main()
