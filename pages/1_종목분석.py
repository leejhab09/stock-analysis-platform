"""
종목 분석 페이지
티커 입력 → 재무지표 + AI 분석 리포트 + 기술적 차트
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from utils.stock_data import (
    get_stock_info, get_price_history, add_technical_indicators,
    get_usd_krw, format_large_number, safe_get
)
from utils.ai_analysis import analyze_stock

st.set_page_config(page_title="종목 분석 | 해외주식", layout="wide")

st.markdown("<h2 style='color:#1a56db;margin-bottom:4px;'>🔍 종목 분석</h2>", unsafe_allow_html=True)
st.markdown("<p style='color:#666;font-size:.85rem;margin-bottom:16px;'>티커를 입력하면 재무지표·기술적 차트·AI 분석 리포트를 자동 생성합니다.</p>", unsafe_allow_html=True)

# ── 입력
with st.form("search_form"):
    col_t, col_p, col_s = st.columns([3, 2, 1])
    with col_t:
        ticker = st.text_input("티커 심볼", value="AAPL", placeholder="예: AAPL, MSFT, NVDA").upper().strip()
    with col_p:
        period = st.selectbox("기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2,
                              format_func=lambda x: {"3mo":"3개월","6mo":"6개월","1y":"1년","2y":"2년","5y":"5년"}[x])
    with col_s:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("분석", use_container_width=True, type="primary")

if not submitted and "last_ticker" not in st.session_state:
    st.info("티커를 입력하고 '분석' 버튼을 클릭하세요.")
    st.stop()

if submitted:
    st.session_state["last_ticker"] = ticker
    st.session_state["last_period"] = period
else:
    ticker = st.session_state.get("last_ticker", "AAPL")
    period = st.session_state.get("last_period", "1y")

# ── 데이터 수집
with st.spinner(f"{ticker} 데이터 수집 중..."):
    info = get_stock_info(ticker)
    hist = get_price_history(ticker, period=period)

if "error" in info or hist.empty:
    st.error(f"'{ticker}' 데이터를 불러올 수 없습니다. 티커를 확인하세요.")
    st.stop()

hist = add_technical_indicators(hist)
fx = get_usd_krw()

# ── KPI
name = safe_get(info, "longName", ticker)
current = safe_get(info, "currentPrice", None)
prev_close = safe_get(info, "previousClose", None)
market_cap = safe_get(info, "marketCap", None)
sector = safe_get(info, "sector", "N/A")
industry = safe_get(info, "industry", "N/A")

st.markdown(f"<h3 style='margin:0 0 12px;color:#0D1B2A;'>{name} <span style='color:#888;font-size:1rem;font-weight:400;'>({ticker})</span></h3>", unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

try:
    price_delta = f"{(float(current)-float(prev_close))/float(prev_close)*100:+.2f}%" if current and prev_close else None
    k1.metric("현재가 (USD)", f"${float(current):,.2f}", price_delta)
    k1.caption(f"≈ ₩{float(current)*fx:,.0f}")
except Exception:
    k1.metric("현재가", str(current))

try:
    k2.metric("시가총액", format_large_number(market_cap))
except Exception:
    k2.metric("시가총액", "N/A")

k3.metric("섹터", sector)
k3.caption(industry)

try:
    pe = info.get("trailingPE")
    k4.metric("PER (TTM)", f"{float(pe):.1f}x" if pe else "N/A")
except Exception:
    k4.metric("PER", "N/A")

try:
    roe = info.get("returnOnEquity")
    k5.metric("ROE", f"{float(roe)*100:.1f}%" if roe else "N/A")
except Exception:
    k5.metric("ROE", "N/A")

try:
    target = info.get("targetMeanPrice")
    upside = (float(target) - float(current)) / float(current) * 100 if target and current else None
    k6.metric("목표주가", f"${float(target):,.2f}" if target else "N/A",
              f"{upside:+.1f}% 상승여력" if upside else None)
except Exception:
    k6.metric("목표주가", "N/A")

# ── 1년 수익률 계산
price_change_1y = None
try:
    if len(hist) >= 2:
        price_change_1y = (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100
except Exception:
    pass

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ══════════════════════════════
# 차트
# ══════════════════════════════
tab_chart, tab_finance, tab_ai = st.tabs(["📊 차트", "📋 재무지표", "🤖 AI 분석"])

with tab_chart:
    # 주가 + 볼린저밴드 + 거래량 + RSI + MACD
    has_bb = "BB_upper" in hist.columns
    has_rsi = "RSI" in hist.columns
    has_macd = "MACD" in hist.columns

    rows = 1 + (1 if has_rsi else 0) + (1 if has_macd else 0)
    row_heights = [0.55] + ([0.2] if has_rsi else []) + ([0.25] if has_macd else [])
    subplot_titles = [f"{ticker} 주가"] + (["RSI (14)"] if has_rsi else []) + (["MACD"] if has_macd else [])

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=row_heights, vertical_spacing=0.04,
                        subplot_titles=subplot_titles)

    # 캔들스틱
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"],
        name="주가", increasing_line_color="#ef4444", decreasing_line_color="#3b82f6"
    ), row=1, col=1)

    if has_bb:
        fig.add_trace(go.Scatter(x=hist.index, y=hist["BB_upper"], name="BB 상단",
                                  line=dict(color="rgba(107,114,128,0.5)", dash="dot", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist["BB_lower"], name="BB 하단",
                                  line=dict(color="rgba(107,114,128,0.5)", dash="dot", width=1),
                                  fill="tonexty", fillcolor="rgba(107,114,128,0.07)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist["BB_mid"], name="BB 중선",
                                  line=dict(color="rgba(107,114,128,0.4)", width=1)), row=1, col=1)

    cur_row = 2
    if has_rsi:
        fig.add_trace(go.Scatter(x=hist.index, y=hist["RSI"], name="RSI",
                                  line=dict(color="#8b5cf6", width=1.5)), row=cur_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", line_width=1, row=cur_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", line_width=1, row=cur_row, col=1)
        cur_row += 1

    if has_macd:
        colors = ["#ef4444" if v >= 0 else "#3b82f6" for v in hist["MACD_diff"].fillna(0)]
        fig.add_trace(go.Bar(x=hist.index, y=hist["MACD_diff"], name="MACD 히스토그램",
                              marker_color=colors, opacity=0.7), row=cur_row, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist["MACD"], name="MACD",
                                  line=dict(color="#f59e0b", width=1.5)), row=cur_row, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist["MACD_signal"], name="Signal",
                                  line=dict(color="#64748b", width=1.5)), row=cur_row, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.02),
                      margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

with tab_finance:
    fc1, fc2 = st.columns(2)
    with fc1:
        st.markdown("**밸류에이션**")
        val_data = {
            "PER (TTM)": safe_get(info, "trailingPE"),
            "선행 PER": safe_get(info, "forwardPE"),
            "PBR": safe_get(info, "priceToBook"),
            "PSR": safe_get(info, "priceToSalesTrailing12Months"),
            "EV/EBITDA": safe_get(info, "enterpriseToEbitda"),
        }
        for k, v in val_data.items():
            try:
                st.metric(k, f"{float(v):.2f}x")
            except Exception:
                st.metric(k, str(v))

    with fc2:
        st.markdown("**수익성 & 성장성**")
        prof_data = {
            "ROE": safe_get(info, "returnOnEquity"),
            "ROA": safe_get(info, "returnOnAssets"),
            "순이익률": safe_get(info, "profitMargins"),
            "매출성장률 (YoY)": safe_get(info, "revenueGrowth"),
            "EPS성장률 (YoY)": safe_get(info, "earningsGrowth"),
        }
        for k, v in prof_data.items():
            try:
                st.metric(k, f"{float(v)*100:.1f}%")
            except Exception:
                st.metric(k, str(v))

    st.markdown("---")
    fc3, fc4 = st.columns(2)
    with fc3:
        st.markdown("**재무 안정성**")
        stab_data = {
            "부채비율 (D/E)": safe_get(info, "debtToEquity"),
            "유동비율": safe_get(info, "currentRatio"),
            "배당수익률": safe_get(info, "dividendYield"),
            "베타": safe_get(info, "beta"),
        }
        for k, v in stab_data.items():
            try:
                fv = float(v)
                if k == "배당수익률":
                    st.metric(k, f"{fv*100:.2f}%")
                elif k in ("부채비율 (D/E)", "유동비율", "베타"):
                    st.metric(k, f"{fv:.2f}")
                else:
                    st.metric(k, f"{fv:.2f}")
            except Exception:
                st.metric(k, str(v))

    with fc4:
        st.markdown("**애널리스트 의견**")
        rec = safe_get(info, "recommendationKey", "N/A").upper()
        num_analysts = safe_get(info, "numberOfAnalystOpinions", "N/A")
        st.metric("컨센서스", rec)
        st.metric("참여 애널리스트", str(num_analysts))
        try:
            tp = float(info.get("targetMeanPrice", 0))
            cp = float(info.get("currentPrice", 1))
            st.metric("평균 목표가", f"${tp:,.2f}", f"{(tp-cp)/cp*100:+.1f}%")
        except Exception:
            st.metric("평균 목표가", "N/A")

with tab_ai:
    st.markdown("**Claude AI 종목 분석 리포트**")
    st.caption("분석에 10~20초 소요됩니다.")
    if st.button("🤖 AI 분석 생성", type="primary"):
        with st.spinner("Claude AI가 분석 중..."):
            report = analyze_stock(ticker, info, price_change_1y)
        st.markdown(report)
        st.caption("⚠️ 본 분석은 AI가 공개 데이터를 바탕으로 생성한 참고 자료입니다. 투자 결정의 책임은 투자자 본인에게 있습니다.")
    else:
        st.info("'AI 분석 생성' 버튼을 클릭하면 Claude AI가 이 종목의 투자 분석 리포트를 작성합니다.")
