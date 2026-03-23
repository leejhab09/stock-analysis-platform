"""
kr_stock_data.py — 국내 주식 데이터 수집 모듈
yfinance 기반, .KS(KOSPI) / .KQ(KOSDAQ) 지원
"""
import yfinance as yf
import pandas as pd
import numpy as np

# 인기 종목 기본 목록
KR_POPULAR = [
    ("005930.KS", "삼성전자",   "반도체"),
    ("000660.KS", "SK하이닉스", "반도체"),
    ("035420.KS", "NAVER",      "IT"),
    ("035720.KS", "카카오",     "IT"),
    ("005380.KS", "현대차",     "자동차"),
    ("051910.KS", "LG화학",     "화학"),
    ("006400.KS", "삼성SDI",    "배터리"),
    ("068270.KS", "셀트리온",   "바이오"),
    ("105560.KS", "KB금융",     "금융"),
    ("055550.KS", "신한지주",   "금융"),
]

def suffix(ticker: str) -> str:
    """티커에 .KS / .KQ 없으면 .KS 추가"""
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return ticker
    return ticker + ".KS"

def analyze_kr_ticker(ticker: str) -> dict | None:
    """국내 종목 기술 지표 분석"""
    try:
        ticker = suffix(ticker)
        t      = yf.Ticker(ticker)
        hist   = t.history(period="1y", interval="1d")
        if len(hist) < 20:
            return None
        hist.index = hist.index.tz_localize(None)

        prev       = hist["Close"].iloc[-2]
        curr       = hist["Close"].iloc[-1]
        change_pct = (curr - prev) / prev * 100
        high_52w   = hist["Close"].max()
        low_52w    = hist["Close"].min()
        drop_52w   = (curr - high_52w) / high_52w * 100
        near_low   = (curr - low_52w)  / low_52w  * 100   # 52주 저가 대비 %

        # RSI (14일)
        delta  = hist["Close"].diff()
        gain   = delta.clip(lower=0).rolling(14).mean()
        loss   = (-delta.clip(upper=0)).rolling(14).mean()
        rs     = gain / loss.replace(0, np.nan)
        rsi    = float((100 - 100 / (1 + rs)).iloc[-1])

        # 이동평균
        ma5    = float(hist["Close"].rolling(5).mean().iloc[-1])
        ma20   = float(hist["Close"].rolling(20).mean().iloc[-1])
        ma60   = float(hist["Close"].rolling(60).mean().iloc[-1])
        ma20_gap = (curr - ma20) / ma20 * 100

        # 거래량 급등 (20일 평균 대비)
        vol_avg20  = float(hist["Volume"].rolling(20).mean().iloc[-1])
        vol_today  = float(hist["Volume"].iloc[-1])
        vol_ratio  = vol_today / vol_avg20 if vol_avg20 > 0 else 1.0

        # 가격제한폭 접근 여부 (-20% 이상)
        near_limit_down = change_pct <= -20.0

        # 볼린저 밴드 %B
        std20     = hist["Close"].rolling(20).std().iloc[-1]
        bb_lower  = ma20 - 2 * std20
        bb_upper  = ma20 + 2 * std20
        bb_pct    = float((curr - bb_lower) / (bb_upper - bb_lower)) if (bb_upper - bb_lower) > 0 else 0.5

        info = t.info
        market = "KOSDAQ" if ticker.endswith(".KQ") else "KOSPI"

        return {
            "ticker":          ticker,
            "name":            info.get("shortName") or info.get("longName") or ticker,
            "market":          market,
            "sector":          info.get("sector", "-"),
            "curr_price":      int(curr),
            "change_pct":      round(change_pct, 2),
            "high_52w":        int(high_52w),
            "low_52w":         int(low_52w),
            "drop_52w":        round(drop_52w, 2),
            "near_low_pct":    round(near_low, 2),
            "rsi":             round(rsi, 1),
            "ma5":             int(ma5),
            "ma20":            int(ma20),
            "ma60":            int(ma60),
            "ma20_gap":        round(ma20_gap, 2),
            "vol_ratio":       round(vol_ratio, 2),
            "bb_pct":          round(bb_pct, 2),
            "near_limit_down": near_limit_down,
        }
    except Exception as e:
        return None

def get_kospi_change() -> float | None:
    """KOSPI 당일 등락률"""
    try:
        hist = yf.Ticker("^KS11").history(period="2d")
        if len(hist) >= 2:
            return round((hist["Close"].iloc[-1] - hist["Close"].iloc[-2])
                         / hist["Close"].iloc[-2] * 100, 2)
    except:
        pass
    return None

def get_kosdaq_change() -> float | None:
    """KOSDAQ 당일 등락률"""
    try:
        hist = yf.Ticker("^KQ11").history(period="2d")
        if len(hist) >= 2:
            return round((hist["Close"].iloc[-1] - hist["Close"].iloc[-2])
                         / hist["Close"].iloc[-2] * 100, 2)
    except:
        pass
    return None
