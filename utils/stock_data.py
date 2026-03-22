"""
stock_data.py
yfinance 기반 주식 데이터 수집 모듈
"""
import yfinance as yf
import pandas as pd
import numpy as np

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


def get_stock_info(ticker: str) -> dict:
    """종목 기본 정보 수집"""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return info
    except Exception as e:
        return {"error": str(e)}


def get_price_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """주가 히스토리 수집"""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        return pd.DataFrame()


def get_financials(ticker: str) -> dict:
    """재무제표 수집"""
    try:
        t = yf.Ticker(ticker)
        return {
            "income_stmt": t.income_stmt,
            "balance_sheet": t.balance_sheet,
            "cashflow": t.cashflow,
        }
    except Exception:
        return {}


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """RSI, MACD, 볼린저밴드 추가"""
    if df.empty or len(df) < 30:
        return df
    df = df.copy()
    if TA_AVAILABLE:
        try:
            df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
            macd = ta.trend.MACD(df["Close"])
            df["MACD"] = macd.macd()
            df["MACD_signal"] = macd.macd_signal()
            df["MACD_diff"] = macd.macd_diff()
            bb = ta.volatility.BollingerBands(df["Close"], window=20)
            df["BB_upper"] = bb.bollinger_hband()
            df["BB_lower"] = bb.bollinger_lband()
            df["BB_mid"] = bb.bollinger_mavg()
        except Exception:
            pass
    else:
        # ta 없을 때 수동 계산
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        ema12 = df["Close"].ewm(span=12).mean()
        ema26 = df["Close"].ewm(span=26).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_signal"] = df["MACD"].ewm(span=9).mean()
        df["MACD_diff"] = df["MACD"] - df["MACD_signal"]
        sma20 = df["Close"].rolling(20).mean()
        std20 = df["Close"].rolling(20).std()
        df["BB_upper"] = sma20 + 2 * std20
        df["BB_lower"] = sma20 - 2 * std20
        df["BB_mid"] = sma20
    return df


def get_usd_krw() -> float:
    """USD/KRW 환율 조회"""
    try:
        fx = yf.Ticker("USDKRW=X")
        hist = fx.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 1350.0  # fallback


def format_large_number(n) -> str:
    """큰 숫자를 읽기 쉬운 형태로"""
    try:
        n = float(n)
        if n >= 1e12:
            return f"${n/1e12:.2f}T"
        if n >= 1e9:
            return f"${n/1e9:.2f}B"
        if n >= 1e6:
            return f"${n/1e6:.2f}M"
        return f"${n:,.0f}"
    except Exception:
        return "N/A"


def safe_get(d: dict, key: str, default="N/A"):
    v = d.get(key, default)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return v
