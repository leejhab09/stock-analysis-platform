"""
pages/5_포트폴리오.py — Paper Trading Portfolio Dashboard
페이퍼 트레이딩 포트폴리오 현황 대시보드
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from datetime import datetime, date

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf

from utils.quant_engine import TICKER_NAMES, CHART_THEME

st.set_page_config(page_title="포트폴리오", page_icon="💼", layout="wide")

# ─── 경로 설정 ───────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(BASE_DIR, "data")
TRADES_FILE = os.path.join(DATA_DIR, "paper_trades.json")

PLOT_BG   = "#FAFAFA"
PAPER_BG  = "#FFFFFF"
FONT_CLR  = "#333333"
GRID_CLR  = "#E5E5E5"
ZERO_CLR  = "#CCCCCC"

# ─── 데이터 로드 ─────────────────────────────────────────────────────────────
def load_trades() -> list[dict]:
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def split_trades(trades: list[dict]):
    open_trades   = [t for t in trades if t.get("status") == "open"]
    closed_trades = [t for t in trades if t.get("status") == "closed"]
    return open_trades, closed_trades


# ─── 현재가 조회 (TTL=60초 캐시) ─────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_current_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    prices: dict[str, float] = {}
    if not tickers:
        return prices
    try:
        raw = yf.download(
            list(tickers),
            period="2d",
            progress=False,
            auto_adjust=True,
        )
        close = raw["Close"] if "Close" in raw.columns else raw
        if isinstance(close, pd.Series):
            # single ticker
            ticker = tickers[0]
            val = close.dropna()
            if not val.empty:
                prices[ticker] = float(val.iloc[-1])
        else:
            for ticker in tickers:
                if ticker in close.columns:
                    col = close[ticker].dropna()
                    if not col.empty:
                        prices[ticker] = float(col.iloc[-1])
    except Exception:
        pass
    # fallback: individual lookup for any missing
    for ticker in tickers:
        if ticker not in prices:
            try:
                hist = yf.Ticker(ticker).history(period="2d")
                if not hist.empty:
                    prices[ticker] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
    return prices


def holding_days(buy_date_str: str) -> int:
    try:
        buy_dt = datetime.strptime(buy_date_str[:10], "%Y-%m-%d").date()
        return (date.today() - buy_dt).days
    except Exception:
        return 0


def holding_days_between(buy_date_str: str, sell_date_str: str) -> int:
    try:
        buy_dt  = datetime.strptime(buy_date_str[:10], "%Y-%m-%d").date()
        sell_dt = datetime.strptime(sell_date_str[:10], "%Y-%m-%d").date()
        return (sell_dt - buy_dt).days
    except Exception:
        return 0


def color_pnl(val: float) -> str:
    if val > 0:
        return "color: #16A34A; font-weight: bold"
    elif val < 0:
        return "color: #DC2626; font-weight: bold"
    return "color: #555555"


# ─── 메인 ────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='color:#333;'>💼 페이퍼 트레이딩 포트폴리오</h2>", unsafe_allow_html=True)
st.markdown("auto_trader.py 자동 기록 기반 · 현재가는 yfinance 실시간 조회 (60초 캐시)")
st.markdown("---")

all_trades = load_trades()

if not all_trades:
    st.info("아직 페이퍼 트레이딩 기록이 없습니다. auto_trader.py 가 실행되면 자동으로 표시됩니다.")
    st.stop()

open_trades, closed_trades = split_trades(all_trades)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 상단 요약 메트릭
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("📊 포트폴리오 요약")

# 총 투자금액 (open)
total_invested = sum(t.get("amount_usd", 0) or 0 for t in open_trades)

# 실현 손익
realized_pnl = sum(t.get("pnl_usd", 0) or 0 for t in closed_trades)

# 미실현 손익 — 현재가 필요
open_tickers = tuple(sorted({t["ticker"] for t in open_trades}))

with st.spinner("현재가 조회 중…"):
    live_prices = fetch_current_prices(open_tickers) if open_tickers else {}

unrealized_pnl = 0.0
for t in open_trades:
    cur = live_prices.get(t["ticker"])
    if cur and t.get("price") and t.get("qty"):
        unrealized_pnl += (cur - t["price"]) * t["qty"]

total_pnl = realized_pnl + unrealized_pnl

# 승률 (closed 기준)
wins = [t for t in closed_trades if (t.get("pnl_usd") or 0) > 0]
win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0

total_trades = len(all_trades)

# 메트릭 표시
col1, col2, col3, col4, col5, col6 = st.columns(6)

def fmt_usd(val: float) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}${val:,.2f}"

col1.metric("총 투자금액 (오픈)", f"${total_invested:,.2f}")
col2.metric("실현 손익", fmt_usd(realized_pnl), delta=f"{fmt_usd(realized_pnl)}")
col3.metric("미실현 손익", fmt_usd(unrealized_pnl), delta=f"{fmt_usd(unrealized_pnl)}")
col4.metric("총 손익", fmt_usd(total_pnl), delta=f"{fmt_usd(total_pnl)}")
col5.metric("승률", f"{win_rate:.1f}%", delta=f"{len(wins)}/{len(closed_trades)} 거래")
col6.metric("총 거래 수", f"{total_trades}건", delta=f"오픈 {len(open_trades)} / 청산 {len(closed_trades)}")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. 오픈 포지션 테이블
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("📂 오픈 포지션")

if not open_trades:
    st.info("현재 보유 중인 오픈 포지션이 없습니다.")
else:
    rows = []
    for t in open_trades:
        ticker   = t.get("ticker", "")
        name     = t.get("name") or TICKER_NAMES.get(ticker, ticker)
        buy_price = t.get("price") or 0.0
        qty      = t.get("qty") or 0.0
        cur_price = live_prices.get(ticker)
        if cur_price and buy_price:
            ret_pct  = (cur_price - buy_price) / buy_price * 100
            unrealized = (cur_price - buy_price) * qty
        else:
            ret_pct  = None
            unrealized = None
        buy_date  = t.get("date", "")[:10]
        hold_d    = holding_days(t.get("date", ""))
        rsi_buy   = t.get("rsi_at_buy")
        vix_buy   = t.get("vix_at_buy")

        rows.append({
            "종목":    ticker,
            "이름":    name,
            "매수가":  buy_price,
            "현재가":  cur_price if cur_price else float("nan"),
            "수익률(%)": ret_pct if ret_pct is not None else float("nan"),
            "평가손익($)": unrealized if unrealized is not None else float("nan"),
            "매수일":  buy_date,
            "보유일":  hold_d,
            "매수RSI": rsi_buy,
            "VIX":     vix_buy,
        })

    df_open = pd.DataFrame(rows)

    def style_open(df: pd.DataFrame) -> pd.io.formats.style.Styler:
        def row_color(row):
            pct = row["수익률(%)"]
            styles = [""] * len(row)
            idx_pct  = df.columns.get_loc("수익률(%)")
            idx_pnl  = df.columns.get_loc("평가손익($)")
            if pd.notna(pct):
                clr = "#16A34A" if pct > 0 else ("#DC2626" if pct < 0 else "#555")
                styles[idx_pct] = f"color: {clr}; font-weight: bold"
                styles[idx_pnl] = f"color: {clr}; font-weight: bold"
            return styles

        return (
            df.style
            .apply(row_color, axis=1)
            .format({
                "매수가":     "${:.2f}",
                "현재가":     "${:.2f}",
                "수익률(%)":  "{:+.2f}%",
                "평가손익($)": "${:+,.2f}",
                "매수RSI":   "{:.1f}",
                "VIX":       "{:.1f}",
            }, na_rep="—")
        )

    st.dataframe(style_open(df_open), use_container_width=True, hide_index=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. 누적 손익 차트
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("📈 누적 실현 손익 추이")

if not closed_trades:
    st.info("청산된 거래가 없어 누적 손익 차트를 표시할 수 없습니다.")
else:
    df_closed_sorted = pd.DataFrame(closed_trades).copy()
    # sell_date 우선, 없으면 date
    df_closed_sorted["_sort_date"] = df_closed_sorted.apply(
        lambda r: r.get("sell_date") or r.get("date") or "", axis=1
    )
    df_closed_sorted = df_closed_sorted.sort_values("_sort_date").reset_index(drop=True)
    df_closed_sorted["pnl_usd_val"] = df_closed_sorted["pnl_usd"].fillna(0).astype(float)
    df_closed_sorted["cum_pnl"] = df_closed_sorted["pnl_usd_val"].cumsum()
    df_closed_sorted["x_label"] = df_closed_sorted["_sort_date"].str[:10]

    fig_cum = go.Figure()

    # fill area — positive/negative coloring via a zero reference
    fig_cum.add_trace(go.Scatter(
        x=df_closed_sorted["x_label"],
        y=df_closed_sorted["cum_pnl"],
        mode="lines+markers",
        name="누적 손익",
        line=dict(color="#1D4ED8", width=2),
        marker=dict(size=6, color="#1D4ED8"),
        fill="tozeroy",
        fillcolor="rgba(29,78,216,0.12)",
    ))

    # 0 기준선
    fig_cum.add_hline(y=0, line_dash="dash", line_color=ZERO_CLR, line_width=1)

    fig_cum.update_layout(
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(color=FONT_CLR),
        xaxis=dict(title="날짜", gridcolor=GRID_CLR, tickangle=-30),
        yaxis=dict(title="누적 손익 (USD)", gridcolor=GRID_CLR, zerolinecolor=ZERO_CLR, tickprefix="$"),
        margin=dict(l=60, r=20, t=30, b=60),
        height=350,
        showlegend=False,
    )

    st.plotly_chart(fig_cum, use_container_width=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. 청산 거래 내역 테이블
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("📋 청산 거래 내역")

if not closed_trades:
    st.info("청산된 거래가 없습니다.")
else:
    closed_rows = []
    for t in sorted(closed_trades, key=lambda x: x.get("sell_date") or x.get("date") or "", reverse=True):
        ticker    = t.get("ticker", "")
        name      = t.get("name") or TICKER_NAMES.get(ticker, ticker)
        buy_price  = t.get("price") or 0.0
        sell_price = t.get("sell_price") or 0.0
        pnl_usd   = t.get("pnl_usd") or 0.0
        pnl_pct   = t.get("pnl_pct") or (
            ((sell_price - buy_price) / buy_price * 100) if buy_price else 0.0
        )
        sell_reason = t.get("sell_reason") or "—"
        buy_date   = (t.get("date") or "")[:10]
        sell_date  = (t.get("sell_date") or "")[:10]
        hold_d     = holding_days_between(t.get("date") or "", t.get("sell_date") or "")

        closed_rows.append({
            "종목":      ticker,
            "이름":      name,
            "매수가":    buy_price,
            "매도가":    sell_price,
            "수익률(%)": pnl_pct,
            "손익($)":   pnl_usd,
            "청산사유":  sell_reason,
            "매수일":    buy_date,
            "매도일":    sell_date,
            "보유일":    hold_d,
        })

    df_closed = pd.DataFrame(closed_rows)

    def style_closed(df: pd.DataFrame) -> pd.io.formats.style.Styler:
        def row_color(row):
            pct = row["수익률(%)"]
            styles = [""] * len(row)
            idx_pct = df.columns.get_loc("수익률(%)")
            idx_pnl = df.columns.get_loc("손익($)")
            clr = "#16A34A" if pct > 0 else ("#DC2626" if pct < 0 else "#555")
            styles[idx_pct] = f"color: {clr}; font-weight: bold"
            styles[idx_pnl] = f"color: {clr}; font-weight: bold"
            return styles

        return (
            df.style
            .apply(row_color, axis=1)
            .format({
                "매수가":    "${:.2f}",
                "매도가":    "${:.2f}",
                "수익률(%)": "{:+.2f}%",
                "손익($)":   "${:+,.2f}",
            }, na_rep="—")
        )

    st.dataframe(style_closed(df_closed), use_container_width=True, hide_index=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. 청산 사유 분포 파이 차트
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("🥧 청산 사유 분포")

if not closed_trades:
    st.info("청산된 거래가 없어 청산 사유 분포를 표시할 수 없습니다.")
else:
    reason_counts: dict[str, int] = {}
    for t in closed_trades:
        reason = t.get("sell_reason") or "기타"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    labels = list(reason_counts.keys())
    values = list(reason_counts.values())

    COLOR_MAP = {
        "익절":    "#16A34A",
        "손절":    "#DC2626",
        "기간청산": "#D97706",
        "기타":    "#6B7280",
    }
    colors = [COLOR_MAP.get(lbl, "#9CA3AF") for lbl in labels]

    col_pie, col_pie_info = st.columns([1, 1])

    with col_pie:
        fig_pie = go.Figure(go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
            textinfo="label+percent+value",
            hoverinfo="label+value+percent",
            textfont=dict(size=13, color="#333"),
        ))
        fig_pie.update_layout(
            plot_bgcolor=PLOT_BG,
            paper_bgcolor=PAPER_BG,
            font=dict(color=FONT_CLR),
            margin=dict(l=20, r=20, t=30, b=20),
            height=320,
            showlegend=True,
            legend=dict(font=dict(color=FONT_CLR)),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_pie_info:
        st.markdown("#### 청산 사유별 손익")
        for reason in labels:
            trades_by_reason = [
                t for t in closed_trades
                if (t.get("sell_reason") or "기타") == reason
            ]
            total_pnl_r = sum(t.get("pnl_usd") or 0 for t in trades_by_reason)
            cnt = len(trades_by_reason)
            emoji = {"익절": "✅", "손절": "❌", "기간청산": "⏰"}.get(reason, "📌")
            color = COLOR_MAP.get(reason, "#6B7280")
            sign = "+" if total_pnl_r >= 0 else ""
            st.markdown(
                f"{emoji} **{reason}** — {cnt}건 · "
                f"<span style='color:{color};font-weight:bold'>{sign}${total_pnl_r:,.2f}</span>",
                unsafe_allow_html=True,
            )

st.markdown("---")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 현재가 60초 캐시")
