"""
quant_engine.py — Shared quantitative engine for Stock Analysis Platform
Multi-Factor Mean Reversion Strategy (Freqtrade-inspired structure)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import streamlit as st

# ─────────────────────────────────────────────
# CHART THEME (Light)
# ─────────────────────────────────────────────
CHART_THEME = dict(
    plot_bgcolor="#FAFAFA",
    paper_bgcolor="#FFFFFF",
    font_color="#333333",
    gridcolor="#E8E8E8",
    zerolinecolor="#CCCCCC",
)

# ─────────────────────────────────────────────
# UNIVERSE
# ─────────────────────────────────────────────
UNIVERSE = {
    "US ETF": [
        "SPY",   # S&P 500
        "QQQ",   # Nasdaq 100
        "IWM",   # Russell 2000
        "DIA",   # Dow Jones
        "VTI",   # Total Market
        "GLD",   # Gold
        "SLV",   # Silver
        "TLT",   # 20Y Treasury
        "IEF",   # 7-10Y Treasury
        "HYG",   # High Yield Bond
        "LQD",   # Investment Grade Bond
        "XLF",   # Financials
        "XLK",   # Technology
        "XLE",   # Energy
        "XLV",   # Healthcare
        "XLI",   # Industrials
        "XLP",   # Consumer Staples
        "XLY",   # Consumer Discretionary
        "ARKK",  # ARK Innovation
        "SOXL",  # Semiconductor 3x
    ],
    "US Stocks": [
        "AAPL",  # Apple
        "MSFT",  # Microsoft
        "NVDA",  # NVIDIA
        "AMZN",  # Amazon
        "GOOGL", # Alphabet
        "META",  # Meta
        "TSLA",  # Tesla
        "NFLX",  # Netflix
        "AMD",   # AMD
        "INTC",  # Intel
        "BABA",  # Alibaba
        "TSM",   # TSMC
        "ASML",  # ASML
        "JPM",   # JPMorgan
        "GS",    # Goldman Sachs
        "BAC",   # Bank of America
        "XOM",   # ExxonMobil
        "CVX",   # Chevron
        "JNJ",   # Johnson & Johnson
        "PFE",   # Pfizer
    ],
    "KR ETF": [
        "069500.KS",  # KODEX 200
        "114800.KS",  # KODEX 인버스
        "122630.KS",  # KODEX 레버리지
        "229200.KS",  # KODEX 코스닥150
        "148020.KS",  # KOSEF 국고채10년
        "139660.KS",  # KODEX 銀행
        "091160.KS",  # KODEX 반도체
        "157490.KS",  # TIGER 미국S&P500
        "133690.KS",  # TIGER 미국나스닥100
        "261240.KS",  # KODEX 미국채울트라30년
    ],
    "KR Stocks": [
        "005930.KS",  # 삼성전자
        "000660.KS",  # SK하이닉스
        "035420.KS",  # NAVER
        "035720.KS",  # 카카오
        "005380.KS",  # 현대차
        "000270.KS",  # 기아
        "068270.KS",  # 셀트리온
        "051910.KS",  # LG화학
        "006400.KS",  # 삼성SDI
        "096770.KS",  # SK이노베이션
        "003550.KS",  # LG
        "012330.KS",  # 현대모비스
        "028260.KS",  # 삼성물산
        "017670.KS",  # SK텔레콤
        "030200.KS",  # KT
    ],
}

# ─────────────────────────────────────────────
# TICKER NAMES
# ─────────────────────────────────────────────
TICKER_NAMES: dict[str, str] = {
    # US ETF
    "SPY":  "SPDR S&P 500 ETF",
    "QQQ":  "Invesco Nasdaq 100 ETF",
    "IWM":  "iShares Russell 2000 ETF",
    "DIA":  "SPDR Dow Jones ETF",
    "VTI":  "Vanguard Total Market ETF",
    "GLD":  "SPDR Gold Shares",
    "SLV":  "iShares Silver Trust",
    "TLT":  "iShares 20Y Treasury ETF",
    "IEF":  "iShares 7-10Y Treasury ETF",
    "HYG":  "iShares High Yield Bond ETF",
    "LQD":  "iShares IG Bond ETF",
    "XLF":  "Financial Select SPDR",
    "XLK":  "Technology Select SPDR",
    "XLE":  "Energy Select SPDR",
    "XLV":  "Health Care Select SPDR",
    "XLI":  "Industrial Select SPDR",
    "XLP":  "Consumer Staples SPDR",
    "XLY":  "Consumer Disc SPDR",
    "ARKK": "ARK Innovation ETF",
    "SOXL": "Direxion Semicon 3x Bull",
    # US Stocks
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corp.",
    "NVDA":  "NVIDIA Corp.",
    "AMZN":  "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "META":  "Meta Platforms",
    "TSLA":  "Tesla Inc.",
    "NFLX":  "Netflix Inc.",
    "AMD":   "Advanced Micro Devices",
    "INTC":  "Intel Corp.",
    "BABA":  "Alibaba Group",
    "TSM":   "Taiwan Semiconductor",
    "ASML":  "ASML Holding",
    "JPM":   "JPMorgan Chase",
    "GS":    "Goldman Sachs",
    "BAC":   "Bank of America",
    "XOM":   "ExxonMobil Corp.",
    "CVX":   "Chevron Corp.",
    "JNJ":   "Johnson & Johnson",
    "PFE":   "Pfizer Inc.",
    # KR ETF
    "069500.KS": "KODEX 200",
    "114800.KS": "KODEX 인버스",
    "122630.KS": "KODEX 레버리지",
    "229200.KS": "KODEX 코스닥150",
    "148020.KS": "KOSEF 국고채10년",
    "139660.KS": "KODEX 은행",
    "091160.KS": "KODEX 반도체",
    "157490.KS": "TIGER 미국S&P500",
    "133690.KS": "TIGER 미국나스닥100",
    "261240.KS": "KODEX 미국채울트라30년",
    # KR Stocks
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "068270.KS": "셀트리온",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "096770.KS": "SK이노베이션",
    "003550.KS": "LG",
    "012330.KS": "현대모비스",
    "028260.KS": "삼성물산",
    "017670.KS": "SK텔레콤",
    "030200.KS": "KT",
}

# ─────────────────────────────────────────────
# STRATEGY INFO (Freqtrade-inspired)
# ─────────────────────────────────────────────
STRATEGY_INFO = {
    "name": "Multi-Factor Mean Reversion",
    "version": "1.0",
    "framework": "Freqtrade-inspired (custom implementation)",
    "description": """
## Multi-Factor Mean Reversion Strategy

### 개요
이 전략은 **Freqtrade** 프레임워크의 철학을 차용한 **멀티팩터 평균회귀(Mean Reversion)** 전략입니다.
Freqtrade의 `populate_indicators` / `populate_buy_trend` / `populate_sell_trend` 구조를 Python으로 직접 구현했습니다.

---

### 📐 진입 조건 (Buy Signal — 3중 합치)

| 조건 | 지표 | 임계값 | 의미 |
|------|------|--------|------|
| ① RSI 과매도 | RSI(14) | < 35 | 단기 과매도 상태 |
| ② MFI 과매도 | MFI(14) | < 35 | 자금흐름 과매도 |
| ③ BB 하단 터치 | Close ≤ BB Lower(20, 2σ) | — | 통계적 하단 이탈 |

**→ 세 조건을 동시 충족할 때만 진입 (3-way Confluence)**

---

### 📤 청산 조건 (Sell Signal)

- **시간 기반 청산**: 진입 후 **10 거래일** 경과
- (향후) RSI > 65 또는 BB 상단 도달 시 조기 청산 (확장 예정)

---

### 🌡️ VIX 레짐 필터

| VIX 구간 | 레짐 | 행동 |
|----------|------|------|
| < 20 | 저변동 (공격적) | 정상 스캔 |
| 20 ~ 30 | 중변동 (신중) | 포지션 축소 권고 |
| ≥ 30 | 고변동 (현금 보유) | 스캔 비활성화 |

---

### 🔧 Freqtrade 구조 대응

```
populate_indicators()  →  get_signals()  (RSI, MFI, BBands 계산)
populate_buy_trend()   →  buy_sig 컬럼  (3중 조건 AND)
populate_sell_trend()  →  run_backtest() (10일 후 청산)
```

---

### 📊 성과 지표
- **승률(Win Rate)**: 양수 수익 거래 비율
- **샤프 비율(Sharpe)**: 평균수익 / 수익표준편차
- **MDD**: 개별 거래 최대 손실
- **누적 수익**: 모든 거래 합산
""",
}

# ─────────────────────────────────────────────
# CORE ENGINE FUNCTIONS
# ─────────────────────────────────────────────

def flatten(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance MultiIndex 컬럼을 단일 레벨로 평탄화"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def get_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    지표 계산 + 신호 생성 (Freqtrade populate_indicators + populate_buy_trend)
    Returns df with columns: rsi, mfi, bb_l, bb_u, bb_m, rsi_sig, mfi_sig, bb_sig, buy_sig
    """
    df = flatten(df.copy())
    if len(df) < 25:
        return df

    # ── Bollinger Bands ──────────────────────────
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is None or bbands.empty:
        return df

    # Dynamic column name lookup (버전별 네이밍 차이 대응)
    bb_l_col = next((c for c in bbands.columns if c.startswith('BBL')), None)
    bb_u_col = next((c for c in bbands.columns if c.startswith('BBU')), None)
    bb_m_col = next((c for c in bbands.columns if c.startswith('BBM')), None)
    if not bb_l_col:
        return df

    df['bb_l'] = bbands[bb_l_col]
    df['bb_u'] = bbands[bb_u_col]
    df['bb_m'] = bbands[bb_m_col]

    # ── RSI & MFI ────────────────────────────────
    df['rsi'] = ta.rsi(df['Close'], length=14)
    df['mfi'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)

    # ── Individual signals ───────────────────────
    df['rsi_sig'] = df['rsi'] < 35
    df['mfi_sig'] = df['mfi'] < 35
    df['bb_sig']  = df['Close'] <= df['bb_l']

    # ── 3-way Confluence ─────────────────────────
    df['buy_sig'] = df['rsi_sig'] & df['mfi_sig'] & df['bb_sig']

    return df


def run_backtest(df: pd.DataFrame, hold_days: int = 10) -> dict | None:
    """
    시간 기반 백테스트 (Freqtrade populate_sell_trend 대응)
    Returns metrics dict or None if no trades
    """
    if 'buy_sig' not in df.columns:
        return None

    trades = []
    for i in range(len(df) - hold_days - 1):
        if not df['buy_sig'].iloc[i]:
            continue
        buy_px  = float(df['Close'].iloc[i])
        sell_px = float(df['Close'].iloc[i + hold_days])
        ret = (sell_px / buy_px - 1) * 100
        trades.append({
            'date':  df.index[i].date(),
            'buy':   buy_px,
            'sell':  sell_px,
            'ret':   ret,
            'rsi':   float(df['rsi'].iloc[i]) if 'rsi' in df.columns else None,
            'mfi':   float(df['mfi'].iloc[i]) if 'mfi' in df.columns else None,
        })

    if not trades:
        return None

    rets = [t['ret'] for t in trades]
    std  = np.std(rets)
    cum  = np.cumsum(rets)

    return {
        "trades":    trades,
        "count":     len(trades),
        "win_rate":  len([r for r in rets if r > 0]) / len(rets) * 100,
        "avg_ret":   np.mean(rets),
        "sharpe":    np.mean(rets) / std if std > 0 else 0,
        "mdd":       min(rets),
        "best":      max(rets),
        "cum_rets":  cum.tolist(),
        "total_ret": sum(rets),
    }


def get_vix() -> tuple[float | None, str, str]:
    """
    VIX 현재값 + 레짐 반환
    Returns: (vix_value, regime_label, regime_color)
    """
    try:
        vix_df = yf.Ticker("^VIX").history(period="5d")
        if vix_df.empty:
            return None, "Unknown", "#888888"
        vix = float(vix_df['Close'].iloc[-1])
        if vix < 20:
            return vix, "저변동 (공격적)", "#00CC66"
        elif vix < 30:
            return vix, "중변동 (신중)", "#FFAA00"
        else:
            return vix, "고변동 (현금 보유)", "#FF4444"
    except Exception:
        return None, "Unknown", "#888888"


# ─────────────────────────────────────────────
# DATA FETCHING (cached)
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    """단일 종목 OHLCV 조회 (5분 캐시)"""
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        return flatten(df)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_batch(tickers: list[str], period: str = "3mo") -> dict[str, pd.DataFrame]:
    """
    배치 다운로드 후 ticker별 DataFrame 반환 (60초 캐시)
    단일 yf.download() 호출로 네트워크 요청 최소화
    """
    if not tickers:
        return {}

    result = {}
    try:
        raw = yf.download(
            tickers, period=period, auto_adjust=True,
            group_by='ticker', progress=False, threads=True
        )
        if isinstance(raw.columns, pd.MultiIndex):
            for tkr in tickers:
                try:
                    sub = raw[tkr].dropna(how='all')
                    if not sub.empty:
                        result[tkr] = sub
                except KeyError:
                    pass
        else:
            # 단일 티커가 리스트로 왔을 때
            if len(tickers) == 1:
                result[tickers[0]] = flatten(raw.dropna(how='all'))
    except Exception:
        pass

    return result


@st.cache_data(ttl=60)
def fetch_index_prices() -> dict:
    """
    주요 지수 현재가 + 등락률 조회
    Returns dict: {name: {price, change_pct, color}}
    """
    indices = {
        "S&P 500":  "^GSPC",
        "NASDAQ":   "^IXIC",
        "DOW":      "^DJI",
        "KOSPI":    "^KS11",
    }
    result = {}
    for name, sym in indices.items():
        try:
            df = yf.Ticker(sym).history(period="5d")
            if len(df) >= 2:
                prev  = float(df['Close'].iloc[-2])
                curr  = float(df['Close'].iloc[-1])
                chg   = (curr / prev - 1) * 100
            elif len(df) == 1:
                curr  = float(df['Close'].iloc[-1])
                chg   = 0.0
            else:
                continue
            result[name] = {
                "price":      curr,
                "change_pct": chg,
                "color":      "#00CC66" if chg >= 0 else "#FF4444",
            }
        except Exception:
            pass
    return result
