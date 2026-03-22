"""
종목 비교 페이지
최대 5개 종목 나란히 비교 + AI 종합 의견
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.stock_data import get_stock_info, get_price_history, safe_get, format_large_number
from utils.ai_analysis import compare_stocks

st.set_page_config(page_title="종목 비교 | 해외주식", layout="wide")

st.markdown("<h2 style='color:#1a56db;margin-bottom:4px;'>⚖️ 종목 비교</h2>", unsafe_allow_html=True)
st.markdown("<p style='color:#666;font-size:.85rem;margin-bottom:16px;'>최대 5개 종목의 주요 지표를 나란히 비교합니다.</p>", unsafe_allow_html=True)

# ── 입력
with st.form("compare_form"):
    cols_input = st.columns(5)
    ticker_inputs = []
    defaults = ["AAPL", "MSFT", "GOOGL", "", ""]
    for i, col in enumerate(cols_input):
        with col:
            t = st.text_input(f"종목 {i+1}", value=defaults[i], placeholder="티커").upper().strip()
            ticker_inputs.append(t)
    period = st.selectbox("비교 기간", ["3mo", "6mo", "1y", "2y"], index=2,
                          format_func=lambda x: {"3mo":"3개월","6mo":"6개월","1y":"1년","2y":"2년"}[x])
    submitted = st.form_submit_button("비교 분석", use_container_width=True, type="primary")

tickers = [t for t in ticker_inputs if t]
if not tickers:
    st.info("종목을 1개 이상 입력하세요.")
    st.stop()

if not submitted and "compare_cache" not in st.session_state:
    st.info("종목을 입력하고 '비교 분석' 버튼을 클릭하세요.")
    st.stop()

if submitted:
    with st.spinner("데이터 수집 중..."):
        infos = {}
        hists = {}
        for t in tickers:
            infos[t] = get_stock_info(t)
            hists[t] = get_price_history(t, period=period)
    st.session_state["compare_cache"] = {"infos": infos, "hists": hists, "tickers": tickers, "period": period}
else:
    cache = st.session_state["compare_cache"]
    infos, hists, tickers = cache["infos"], cache["hists"], cache["tickers"]

COLORS = ["#1a56db", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6"]
FILL_COLORS = [
    "rgba(26,86,219,0.15)", "rgba(239,68,68,0.15)", "rgba(16,185,129,0.15)",
    "rgba(245,158,11,0.15)", "rgba(139,92,246,0.15)"
]

# ── 주가 추이 비교 차트
st.markdown("### 주가 추이 비교 (정규화, 시작=100)")
fig = go.Figure()
for i, t in enumerate(tickers):
    h = hists.get(t)
    if h is not None and not h.empty:
        norm = h["Close"] / h["Close"].iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=h.index, y=norm, name=t,
            line=dict(color=COLORS[i % len(COLORS)], width=2)
        ))
fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0),
                  yaxis_title="상대 수익률 (시작=100)",
                  legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, use_container_width=True)

# ── 지표 비교 테이블
st.markdown("### 주요 지표 비교")

METRICS = [
    ("현재가 (USD)", lambda info: f"${float(info.get('currentPrice',0)):,.2f}" if info.get('currentPrice') else "N/A"),
    ("시가총액", lambda info: format_large_number(info.get("marketCap"))),
    ("PER (TTM)", lambda info: f"{float(info.get('trailingPE',0)):.1f}x" if info.get('trailingPE') else "N/A"),
    ("선행 PER", lambda info: f"{float(info.get('forwardPE',0)):.1f}x" if info.get('forwardPE') else "N/A"),
    ("PBR", lambda info: f"{float(info.get('priceToBook',0)):.2f}x" if info.get('priceToBook') else "N/A"),
    ("ROE", lambda info: f"{float(info.get('returnOnEquity',0))*100:.1f}%" if info.get('returnOnEquity') else "N/A"),
    ("순이익률", lambda info: f"{float(info.get('profitMargins',0))*100:.1f}%" if info.get('profitMargins') else "N/A"),
    ("매출성장률", lambda info: f"{float(info.get('revenueGrowth',0))*100:.1f}%" if info.get('revenueGrowth') else "N/A"),
    ("배당수익률", lambda info: f"{float(info.get('dividendYield',0))*100:.2f}%" if info.get('dividendYield') else "0%"),
    ("베타", lambda info: f"{float(info.get('beta',0)):.2f}" if info.get('beta') else "N/A"),
    ("52주 고점", lambda info: f"${float(info.get('fiftyTwoWeekHigh',0)):,.2f}" if info.get('fiftyTwoWeekHigh') else "N/A"),
    ("52주 저점", lambda info: f"${float(info.get('fiftyTwoWeekLow',0)):,.2f}" if info.get('fiftyTwoWeekLow') else "N/A"),
    ("애널리스트 의견", lambda info: safe_get(info, "recommendationKey", "N/A").upper()),
    ("목표주가", lambda info: f"${float(info.get('targetMeanPrice',0)):,.2f}" if info.get('targetMeanPrice') else "N/A"),
    ("섹터", lambda info: safe_get(info, "sector", "N/A")),
]

rows = {}
for label, fn in METRICS:
    row = {}
    for t in tickers:
        try:
            row[t] = fn(infos.get(t, {}))
        except Exception:
            row[t] = "N/A"
    rows[label] = row

df_table = pd.DataFrame(rows, index=tickers).T
st.dataframe(df_table, use_container_width=True)

# ── 레이더 차트
st.markdown("### 밸류에이션·수익성 레이더 비교")

def norm_val(v, reverse=False):
    try:
        v = float(v)
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.5

categories = ["ROE", "순이익률", "매출성장률", "배당수익률"]
fig_r = go.Figure()
for i, t in enumerate(tickers):
    info = infos.get(t, {})
    try:
        vals = [
            min(float(info.get("returnOnEquity", 0)) * 100 / 50, 1.0),
            min(float(info.get("profitMargins", 0)) * 100 / 40, 1.0),
            min(float(info.get("revenueGrowth", 0)) * 100 / 30, 1.0),
            min(float(info.get("dividendYield", 0)) * 100 / 5, 1.0),
        ]
    except Exception:
        vals = [0, 0, 0, 0]
    fig_r.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=categories + [categories[0]],
        fill="toself", name=t,
        line=dict(color=COLORS[i % len(COLORS)]),
        fillcolor=FILL_COLORS[i % len(FILL_COLORS)],
        opacity=0.7,
    ))
fig_r.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    height=380, margin=dict(l=20, r=20, t=30, b=20),
    legend=dict(orientation="h", y=-0.05),
)
st.plotly_chart(fig_r, use_container_width=True)

# ── AI 비교 분석
st.markdown("---")
st.markdown("### 🤖 AI 종목 비교 분석")
if st.button("AI 종합 의견 생성", type="primary"):
    with st.spinner("Claude AI 비교 분석 중..."):
        report = compare_stocks(tickers, infos)
    st.markdown(report)
    st.caption("⚠️ AI 참고 자료입니다. 투자 책임은 투자자 본인에게 있습니다.")
else:
    st.info("'AI 종합 의견 생성' 버튼을 클릭하면 Claude AI가 종목별 비교 분석을 작성합니다.")
