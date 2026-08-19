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


INDUSTRY_CSV_URL = (
    "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
)


def fetch_industry_map() -> dict[str, dict[str, str]]:
    """symbol -> {name, industry, marketCap, volume}"""
    out: dict[str, dict[str, str]] = {}
    try:
        req = Request(INDUSTRY_CSV_URL, headers={"User-Agent": "Mozilla/5.0 rs-screener"})
        with urlopen(req, timeout=60) as res:
            text = res.read().decode("utf-8", errors="ignore")
        import csv
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            sym = (row.get("symbol") or "").strip().upper()
            if not sym:
                continue
            out[sym] = {
                "name": (row.get("name") or sym).strip(),
                "industry": (row.get("industry") or "—").strip() or "—",
                "marketCap": row.get("marketCap") or "",
                "volume": row.get("volume") or "",
            }
        print(f"Industry map size: {len(out)}")
    except Exception as e:
        print(f"Industry map fetch failed: {e}")
    return out


def auto_theme_from_industry(industry: str, ticker: str, themes: dict[str, list[str]]) -> str:
    """明示テーマ優先、なければ業種から詳細テーマへ自動分類"""
    for name, members in themes.items():
        if ticker in members:
            return name

    ind = (industry or "").lower().strip()
    if not ind or ind in {"—", "-", "n/a", "nan", "none", "null", "未分類"}:
        return "未分類"

    rules = [
        # ===== Tech 詳細 =====
        ("サイバーセキュリティ", ["cyber", "security software", "network security", "security & protection"]),
        ("AI/半導体", ["semiconductor", "semiconductors", "chip", "electronic equipment", "electronics manufacturing", "electronic components"]),
        ("クラウド / データ", ["software—infrastructure", "software - infrastructure", "infrastructure software", "data processing", "cloud", "data storage"]),
        ("業務ソフト", ["application software", "enterprise software"]),
        ("ITサービス", ["information technology services", "it services", "consulting services"]),
        ("インターネット", ["internet content", "internet retail", "interactive media", "online media"]),
        ("ハード・端末", ["consumer electronics", "technology hardware", "computer hardware", "computer equipment"]),
        ("通信機器", ["communications equipment", "communication equipment"]),
        ("通信キャリア", ["telecom", "wireless telecommunication", "telephone", "integrated telecommunication"]),
        ("テクノロジー", ["technology", "information technology", "tech"]),
        # ===== Health =====
        ("バイオテック", ["biotech", "biotechnology"]),
        ("製薬", ["pharma", "drug manufacturer", "pharmaceutical"]),
        ("医療機器", ["medical device", "medical instruments", "diagnostics", "health care equipment", "medical distribution", "medical supplies"]),
        ("医療サービス", ["health care providers", "hospital", "health services", "managed health", "health care facilities"]),
        ("ヘルスケア", ["health care", "healthcare", "health"]),
        # ===== Financials =====
        ("銀行", ["bank", "banks", "diversified bank", "regional bank", "thrifts", "savings"]),
        ("保険", ["insurance", "insurer", "life insurance", "property & casualty", "property and casualty", "reinsurance"]),
        ("証券・資産運用", ["capital market", "asset management", "investment banking", "broker", "financial exchanges", "investment"]),
        ("決済・フィンテック", ["fintech", "financial technology", "transaction & payment", "payment", "credit services"]),
        ("金融その他", ["financial", "mortgage", "consumer finance", "financials"]),
        # ===== Energy / Utility / RE =====
        ("石油・ガス", ["oil", "gas", "petroleum", "exploration", "upstream", "midstream", "downstream", "oil & gas"]),
        ("エネルギーその他", ["energy", "coal", "renewable", "solar", "wind"]),
        ("電力・ユーティリティ", ["utilit", "electric", "water utilities", "gas utility", "independent power", "multi-utilities"]),
        ("REIT・不動産", ["reit", "real estate"]),
        # ===== Industrials =====
        ("機械", ["machinery", "industrial machinery", "farm & construction"]),
        ("建設・土木", ["construction", "engineering", "building product", "building materials"]),
        ("防衛・航空宇宙", ["aerospace", "defense", "defence"]),
        ("運輸・物流", ["airline", "air freight", "railroad", "shipping", "logistics", "truck", "transport", "marine"]),
        ("資本財・産業", ["industrial conglomerate", "industrials", "industrial", "trading companies", "distributors industrial"]),
        # ===== Materials =====
        ("化学", ["chemical", "specialty chemical"]),
        ("金属・鉱業", ["metal", "mining", "steel", "aluminum", "copper", "gold", "silver", "precious"]),
        ("素材その他", ["paper", "materials", "containers", "packaging", "forest"]),
        # ===== Consumer =====
        ("自動車", ["auto manufacturer", "automobile", "auto parts", "car dealer", "vehicle"]),
        ("小売", ["specialty retail", "retail", "department", "home improvement", "apparel retail"]),
        ("EC・通販", ["internet retail", "e-commerce"]),
        ("外食", ["restaurant", "restaurants"]),
        ("旅行・レジャー", ["leisure", "hotel", "resorts", "travel", "casinos", "gaming", "entertainment"]),
        ("食品・飲料", ["beverage", "soft drink", "packaged foods", "food products", "food distribution", "brewer"]),
        ("生活用品", ["household", "personal product", "personal care", "household products"]),
        ("アパレル", ["apparel", "footwear", "textiles", "luxury goods"]),
        ("消費財", ["consumer staples", "consumer defensive", "tobacco", "consumer goods"]),
        ("消費関連", ["consumer discretionary", "consumer cyclical"]),
        # ===== Media / Other =====
        ("メディア・広告", ["media", "publishing", "broadcasting", "advertising", "movies", "entertainment"]),
        ("通信サービス", ["communication services"]),
        ("教育", ["education", "education & training"]),
        ("ビジネスサービス", ["business services", "commercial services", "staffing"]),
    ]

    for theme, keys in rules:
        if any(k in ind for k in keys):
            return theme

    return "未分類"


    # 具体キーワード → 広義セクター の順
    rules = [
        # Tech 詳細
        ("サイバーセキュリティ", ["cyber", "security software", "network security", "security &"]),
        ("AI/半導体", ["semiconductor", "semiconductors", "chip", "electronic equipment", "electronics manufacturing"]),
        ("クラウド / データ", ["software—infrastructure", "software - infrastructure", "data processing", "cloud", "infrastructure software"]),
        ("ソフトウェア", ["software", "application software", "information technology services", "it services"]),
        ("インターネット", ["internet content", "internet retail", "interactive media", "online media", "e-commerce"]),
        ("メガテック", ["consumer electronics", "technology hardware", "computer hardware"]),
        ("通信", ["telecom", "wireless telecommunication", "telephone", "communications equipment"]),
        # Health
        ("バイオテック", ["biotech", "biotechnology"]),
        ("製薬", ["pharma", "drug manufacturer", "pharmaceutical"]),
        ("医療機器", ["medical device", "medical instruments", "diagnostics", "health care equipment", "medical distribution"]),
        ("ヘルスケア", ["health care", "healthcare", "hospital", "health services", "managed health", "health care providers"]),
        # Financials
        ("銀行", ["bank", "banks", "diversified bank", "regional bank", "thrifts"]),
        ("保険", ["insurance", "insurer", "life insurance", "property & casualty", "property and casualty"]),
        ("証券・資産運用", ["capital market", "asset management", "investment banking", "broker", "financial exchanges"]),
        ("フィンテック", ["fintech", "financial technology", "transaction & payment", "payment"]),
        ("金融その他", ["financial", "credit services", "mortgage", "consumer finance", "financials"]),
        # Cyclical
        ("エネルギー", ["oil", "gas", "energy", "petroleum", "exploration", "coal"]),
        ("電力・ユーティリティ", ["utilit", "electric", "water utilities", "gas utility", "independent power"]),
        ("不動産", ["reit", "real estate"]),
        ("資本財・機械", ["machinery", "industrial conglomerate", "construction", "building product", "industrials", "industrial"]),
        ("素材・化学", ["chemical", "metal", "mining", "steel", "paper", "materials", "aluminum", "copper", "gold"]),
        ("自動車", ["auto", "automobile", "vehicle", "car dealer", "auto parts"]),
        ("航空・運輸", ["airline", "air freight", "railroad", "shipping", "logistics", "truck", "transport"]),
        ("防衛・航空宇宙", ["aerospace", "defense", "defence"]),
        # Consumer
        ("小売", ["retail", "specialty retail", "department", "distributors"]),
        ("外食・レジャー", ["restaurant", "leisure", "hotel", "gaming", "entertainment", "resorts", "casinos"]),
        ("消費財", ["beverage", "food", "household", "personal product", "tobacco", "apparel", "footwear", "packaged foods", "soft drink", "consumer staples", "consumer defensive"]),
        ("メディア", ["media", "publishing", "broadcasting", "advertising", "movies", "communication services"]),
        # 広義セクター名（マスタがセクターのみのとき）
        ("テクノロジー", ["technology", "information technology", "tech"]),
        ("消費関連", ["consumer discretionary", "consumer cyclical"]),
        ("ヘルスケア", ["health"]),
    ]

    for theme, keys in rules:
        if any(k in ind for k in keys):
            return theme

    return "その他"


    # 具体度の高い順（約30テーマ）
    rules = [
        # Tech
        ("サイバーセキュリティ", ["cyber", "security software", "security &", "network security"]),
        ("AI/半導体", ["semiconductor", "semiconductors", "chip", "electronic equipment", "electronics"]),
        ("クラウド / データ", ["software—infrastructure", "software - infrastructure", "data processing", "cloud"]),
        ("ソフトウェア", ["software", "information technology services", "it services", "application software"]),
        ("インターネット", ["internet", "interactive media", "online media", "internet content"]),
        ("メガテック", ["consumer electronics", "technology hardware", "computer hardware"]),
        ("通信", ["telecom", "communication services", "wireless", "telephone", "communications"]),
        # Health
        ("バイオテック", ["biotech", "biotechnology"]),
        ("製薬", ["pharma", "drug manufacturer", "pharmaceutical", "pharmaceuticals"]),
        ("医療機器", ["medical device", "medical instruments", "diagnostics", "health care equipment", "medical distribution"]),
        ("ヘルスケア", ["health care", "healthcare", "hospital", "health services", "managed health", "health care providers"]),
        # Financials
        ("銀行", ["bank", "banks", "diversified bank", "regional bank", "thrifts"]),
        ("保険", ["insurance", "insurer", "life insurance", "property & casualty", "property and casualty"]),
        ("証券・資産運用", ["capital market", "asset management", "investment banking", "broker", "financial exchanges"]),
        ("フィンテック", ["fintech", "financial technology", "transaction & payment", "payment"]),
        ("金融その他", ["financial", "credit services", "mortgage", "consumer finance"]),
        # Cyclical / Industrial
        ("エネルギー", ["oil", "gas", "energy", "petroleum", "exploration", "coal"]),
        ("電力・ユーティリティ", ["utilit", "electric", "water utilities", "gas utility", "independent power"]),
        ("不動産", ["reit", "real estate"]),
        ("資本財・機械", ["machinery", "industrial conglomerate", "construction & engineering", "building product", "industrial"]),
        ("素材・化学", ["chemical", "metal", "mining", "steel", "paper", "commodity", "materials", "aluminum", "copper", "gold"]),
        ("自動車", ["auto", "automobile", "vehicle", "car dealer", "auto parts"]),
        ("航空・運輸", ["airline", "air freight", "railroad", "shipping", "logistics", "truck", "transport"]),
        ("防衛・航空宇宙", ["aerospace", "defense", "defence"]),
        # Consumer
        ("小売", ["retail", "store", "department", "e-commerce", "internet retail", "specialty retail"]),
        ("外食・レジャー", ["restaurant", "leisure", "hotel", "gaming", "entertainment", "resorts"]),
        ("消費財", ["beverage", "food", "household", "personal product", "tobacco", "apparel", "footwear", "packaged foods", "soft drink"]),
        ("メディア", ["media", "publishing", "broadcasting", "advertising", "movies"]),
        ("テクノロジー", ["technology", "tech"]),
    ]

    for theme, keys in rules:
        if any(k in ind for k in keys):
            return theme

    return "その他"





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


def _normalize_ohlcv(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame | None:
    """yfinanceの列形式の違いを吸収して OHLCV に揃える"""
    if df is None or df.empty:
        return None

    out = df.copy()
    # MultiIndex 対応: ('Close','SPY') or ('SPY','Close')
    if isinstance(out.columns, pd.MultiIndex):
        lvl0 = out.columns.get_level_values(0)
        lvl1 = out.columns.get_level_values(1)
        if ticker is not None and ticker in lvl0:
            out = out[ticker].copy()
        elif ticker is not None and ticker in lvl1:
            out.columns = lvl0
            # already price names on level 0 with ticker on level1 - drop to price
            try:
                out = df.xs(ticker, axis=1, level=1).copy()
            except Exception:
                # fallback: rename by matching
                cols = {}
                for a, b in df.columns:
                    if b == ticker:
                        cols[(a, b)] = a
                    elif a == ticker:
                        cols[(a, b)] = b
                out = df.rename(columns=cols)
                out.columns = [c if not isinstance(c, tuple) else c[0] for c in out.columns]
        else:
            # single ticker download often is Price x Ticker
            try:
                if len(set(lvl1)) == 1:
                    out.columns = lvl0
                elif len(set(lvl0)) == 1:
                    out.columns = lvl1
            except Exception:
                return None

    # 列名を文字列化
    out.columns = [str(c) for c in out.columns]
    # Adj Close しかない場合の保険
    if "Close" not in out.columns and "Adj Close" in out.columns:
        out["Close"] = out["Adj Close"]
    if "Close" not in out.columns:
        return None
    for col in ("Open", "High", "Low"):
        if col not in out.columns:
            out[col] = out["Close"]
    if "Volume" not in out.columns:
        out["Volume"] = 0
    out = out.dropna(subset=["Close"]).dropna(how="all")
    return out if not out.empty else None


def download_history_batch(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    if not tickers:
        return data
    try:
        df = yf.download(
            tickers if len(tickers) > 1 else tickers[0],
            period=period,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"download error: {e}")
        return data

    if not isinstance(df, pd.DataFrame) or df.empty:
        return data

    if len(tickers) == 1:
        t = tickers[0]
        norm = _normalize_ohlcv(df, t)
        if norm is not None:
            data[t] = norm
        return data

    for t in tickers:
        try:
            norm = _normalize_ohlcv(df, t)
            if norm is not None:
                data[t] = norm
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
    # 定義テーマ + 実際に付いたテーマを集計
    theme_names = list(themes.keys())
    for s in stocks:
        if s.get("theme") and s["theme"] not in theme_names:
            theme_names.append(s["theme"])

    result = []
    for name in theme_names:
        rows = [s for s in stocks if s.get("theme") == name]
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
    industry_map = fetch_industry_map()
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

            info = industry_map.get(t, {})
            industry = (info.get("industry") or "").strip()
            if not industry or industry in {"—", "-", "N/A", "n/a"}:
                industry = "—"
            name = info.get("name", t) or t
            theme = auto_theme_from_industry(industry, t, themes)
            meta_rows.append(
                {
                    "ticker": t,
                    "name": name,
                    "stage": stage,
                    "tt": tt,
                    "industry": industry,
                    "theme": theme,
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
