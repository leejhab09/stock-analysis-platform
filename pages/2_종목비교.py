"""
종목 비교 페이지 — 미국 / 국내 통합
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.stock_data import get_stock_info, get_price_history, safe_get, format_large_number, get_usd_krw
from utils.ai_analysis import compare_stocks
from utils.kr_stock_data import suffix as kr_suffix, KR_POPULAR

st.set_page_config(page_title="종목 비교", layout="wide")

# ── 시장 선택
market = st.radio("시장", ["🇺🇸 미국", "🇰🇷 국내"], horizontal=True,
                  label_visibility="collapsed")
IS_KR = (market == "🇰🇷 국내")

if IS_KR:
    st.markdown("<h2 style='color:#c0392b;background:#FFF0F0;padding:10px 16px;"
                "border-radius:8px;border-left:5px solid #c0392b;'>🇰🇷 국내 종목 비교</h2>",
                unsafe_allow_html=True)
    st.caption("KOSPI/KOSDAQ · 티커: 6자리 숫자 (예: 005930, 000660)")
    with st.expander("📌 인기 종목"):
        cols = st.columns(5)
        for i,(tk,name,sector) in enumerate(KR_POPULAR):
            cols[i%5].markdown(f"**{tk.replace('.KS','')}** {name} _{sector}_")
else:
    st.markdown("<h2 style='color:#1a56db;background:#EBF5FF;padding:10px 16px;"
                "border-radius:8px;border-left:5px solid #1a56db;'>🇺🇸 미국 종목 비교</h2>",
                unsafe_allow_html=True)
    st.caption("NYSE/NASDAQ · 최대 5개 종목 비교")

st.markdown("<p style='color:#666;font-size:.85rem;'>최대 5개 종목의 주요 지표를 나란히 비교합니다.</p>",
            unsafe_allow_html=True)

defaults_us = ["AAPL","MSFT","GOOGL","",""]
defaults_kr = ["005930","000660","035420","",""]
defaults    = defaults_kr if IS_KR else defaults_us
placeholder = "예: 005930" if IS_KR else "예: AAPL"

with st.form("compare_form"):
    cols_input = st.columns(5)
    ticker_inputs = []
    for i,col in enumerate(cols_input):
        with col:
            t = col.text_input(f"종목 {i+1}", value=defaults[i],
                               placeholder=placeholder).strip()
            ticker_inputs.append(t)
    period = st.selectbox("비교 기간", ["3mo","6mo","1y","2y"], index=2,
                          format_func=lambda x:{"3mo":"3개월","6mo":"6개월","1y":"1년","2y":"2년"}[x])
    submitted = st.form_submit_button("비교 분석", use_container_width=True, type="primary")

def normalize(t, is_kr):
    t = t.upper().strip()
    return kr_suffix(t) if is_kr else t

tickers = [normalize(t, IS_KR) for t in ticker_inputs if t.strip()]
if not tickers:
    st.info("종목을 1개 이상 입력하세요.")
    st.stop()

if not submitted and "compare_cache" not in st.session_state:
    st.info("종목 입력 후 '비교 분석' 버튼을 클릭하세요.")
    st.stop()

if submitted:
    with st.spinner("데이터 수집 중..."):
        infos = {t: get_stock_info(t) for t in tickers}
        hists = {t: get_price_history(t, period=period) for t in tickers}
    st.session_state["compare_cache"] = {"infos":infos,"hists":hists,
                                          "tickers":tickers,"period":period,"is_kr":IS_KR}
else:
    c = st.session_state["compare_cache"]
    infos,hists,tickers,IS_KR = c["infos"],c["hists"],c["tickers"],c["is_kr"]

COLORS      = ["#1a56db","#ef4444","#10b981","#f59e0b","#8b5cf6"]
FILL_COLORS = ["rgba(26,86,219,0.15)","rgba(239,68,68,0.15)","rgba(16,185,129,0.15)",
               "rgba(245,158,11,0.15)","rgba(139,92,246,0.15)"]

fx = get_usd_krw()

# ── 주가 추이 비교
st.markdown("### 주가 추이 비교 (정규화, 시작=100)")
fig = go.Figure()
for i,t in enumerate(tickers):
    h = hists.get(t)
    if h is not None and not h.empty:
        norm = h["Close"] / h["Close"].iloc[0] * 100
        fig.add_trace(go.Scatter(x=h.index, y=norm, name=t.replace(".KS","").replace(".KQ",""),
                                  line=dict(color=COLORS[i%len(COLORS)], width=2)))
fig.update_layout(height=320, margin=dict(l=0,r=0,t=20,b=0),
                  yaxis_title="상대 수익률 (시작=100)",
                  legend=dict(orientation="h",y=1.05))
st.plotly_chart(fig, use_container_width=True)

# ── 지표 비교 테이블
st.markdown("### 주요 지표 비교")

def price_str(info, is_kr, fx):
    try:
        p = info.get("currentPrice") or info.get("regularMarketPrice")
        return f"₩{float(p):,.0f}" if is_kr else f"${float(p):,.2f}"
    except: return "N/A"

def cap_str(info, is_kr):
    mc = info.get("marketCap")
    if not mc: return "N/A"
    try:
        mc = float(mc)
        return f"₩{mc/1e12:.1f}조" if is_kr else format_large_number(mc)
    except: return "N/A"

METRICS = [
    ("현재가",          lambda i: price_str(i, IS_KR, fx)),
    ("시가총액",         lambda i: cap_str(i, IS_KR)),
    ("PER (TTM)",      lambda i: f"{float(i.get('trailingPE',0)):.1f}x" if i.get('trailingPE') else "N/A"),
    ("선행 PER",        lambda i: f"{float(i.get('forwardPE',0)):.1f}x" if i.get('forwardPE') else "N/A"),
    ("PBR",            lambda i: f"{float(i.get('priceToBook',0)):.2f}x" if i.get('priceToBook') else "N/A"),
    ("ROE",            lambda i: f"{float(i.get('returnOnEquity',0))*100:.1f}%" if i.get('returnOnEquity') else "N/A"),
    ("순이익률",         lambda i: f"{float(i.get('profitMargins',0))*100:.1f}%" if i.get('profitMargins') else "N/A"),
    ("매출성장률",        lambda i: f"{float(i.get('revenueGrowth',0))*100:.1f}%" if i.get('revenueGrowth') else "N/A"),
    ("배당수익률",        lambda i: f"{float(i.get('dividendYield',0))*100:.2f}%" if i.get('dividendYield') else "0%"),
    ("베타",            lambda i: f"{float(i.get('beta',0)):.2f}" if i.get('beta') else "N/A"),
    ("52주 고점",        lambda i: (f"₩{float(i.get('fiftyTwoWeekHigh',0)):,.0f}" if IS_KR
                                   else f"${float(i.get('fiftyTwoWeekHigh',0)):,.2f}") if i.get('fiftyTwoWeekHigh') else "N/A"),
    ("52주 저점",        lambda i: (f"₩{float(i.get('fiftyTwoWeekLow',0)):,.0f}" if IS_KR
                                   else f"${float(i.get('fiftyTwoWeekLow',0)):,.2f}") if i.get('fiftyTwoWeekLow') else "N/A"),
    ("애널리스트 의견",   lambda i: safe_get(i,"recommendationKey","N/A").upper()),
    ("섹터",            lambda i: safe_get(i,"sector","N/A")),
]

rows = {}
display_names = [t.replace(".KS","").replace(".KQ","") for t in tickers]
for label,fn in METRICS:
    row = {}
    for t,dn in zip(tickers,display_names):
        try:   row[dn] = fn(infos.get(t,{}))
        except:row[dn] = "N/A"
    rows[label] = row

st.dataframe(pd.DataFrame(rows, index=display_names).T, use_container_width=True)

# ── 레이더 차트
st.markdown("### 수익성 레이더 비교")
categories = ["ROE","순이익률","매출성장률","배당수익률"]
fig_r = go.Figure()
for i,(t,dn) in enumerate(zip(tickers,display_names)):
    info = infos.get(t,{})
    try:
        vals = [
            min(float(info.get("returnOnEquity",0))*100/50, 1.0),
            min(float(info.get("profitMargins",0))*100/40, 1.0),
            min(float(info.get("revenueGrowth",0))*100/30, 1.0),
            min(float(info.get("dividendYield",0))*100/5,  1.0),
        ]
    except: vals = [0,0,0,0]
    fig_r.add_trace(go.Scatterpolar(
        r=vals+[vals[0]], theta=categories+[categories[0]],
        fill="toself", name=dn,
        line=dict(color=COLORS[i%len(COLORS)]),
        fillcolor=FILL_COLORS[i%len(FILL_COLORS)], opacity=0.7,
    ))
fig_r.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,1])),
                    height=380, legend=dict(orientation="h",y=-0.05))
st.plotly_chart(fig_r, use_container_width=True)

# ── AI 비교 분석
st.markdown("---")
st.markdown("### 🤖 AI 종목 비교 분석")
if st.button("AI 종합 의견 생성", type="primary"):
    with st.spinner("Claude AI 분석 중..."):
        report = compare_stocks(tickers, infos)
    st.markdown(report)
    st.caption("⚠️ AI 참고 자료입니다.")
else:
    st.info("버튼 클릭 시 Claude AI가 종목별 비교 분석을 작성합니다.")
