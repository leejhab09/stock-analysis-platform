"""
종목 분석 페이지 — 미국 / 국내 통합
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from numpy import nan

from utils.stock_data import (
    get_stock_info, get_price_history, add_technical_indicators,
    get_usd_krw, format_large_number, safe_get
)
from utils.ai_analysis import analyze_stock
from utils.kr_stock_data import suffix as kr_suffix, KR_POPULAR

st.set_page_config(page_title="종목 분석", layout="wide")

# ── 시장 선택
market = st.radio("시장", ["🇺🇸 미국", "🇰🇷 국내"], horizontal=True,
                  label_visibility="collapsed")
IS_KR = (market == "🇰🇷 국내")

if IS_KR:
    st.markdown("<h2 style='color:#c0392b;background:#FFF0F0;padding:10px 16px;"
                "border-radius:8px;border-left:5px solid #c0392b;'>🇰🇷 국내 종목 분석</h2>",
                unsafe_allow_html=True)
    st.caption("KOSPI/KOSDAQ · 티커: 6자리 숫자 (예: 005930) 또는 005930.KS")
    with st.expander("📌 인기 종목"):
        cols = st.columns(5)
        for i,(tk,name,sector) in enumerate(KR_POPULAR):
            cols[i%5].markdown(f"**{tk.replace('.KS','')}** {name}")
else:
    st.markdown("<h2 style='color:#1a56db;background:#EBF5FF;padding:10px 16px;"
                "border-radius:8px;border-left:5px solid #1a56db;'>🇺🇸 미국 종목 분석</h2>",
                unsafe_allow_html=True)
    st.caption("NYSE/NASDAQ · 티커: 영문 (예: AAPL, NVDA, MSFT)")

st.markdown("<p style='color:#666;font-size:.85rem;'>티커 입력 → 재무지표·차트·AI 리포트 자동 생성</p>",
            unsafe_allow_html=True)

default_ticker = "005930" if IS_KR else "AAPL"
with st.form("search_form"):
    c1,c2,c3 = st.columns([3,2,1])
    with c1:
        ticker_input = st.text_input("티커", value=default_ticker,
                                      placeholder="예: 005930" if IS_KR else "예: AAPL").strip()
    with c2:
        period = st.selectbox("기간", ["3mo","6mo","1y","2y","5y"], index=2,
                              format_func=lambda x:{"3mo":"3개월","6mo":"6개월","1y":"1년","2y":"2년","5y":"5년"}[x])
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("분석", use_container_width=True, type="primary")

def normalize(t, is_kr):
    t = t.upper().strip()
    return kr_suffix(t) if is_kr else t

if not submitted and "last_ticker" not in st.session_state:
    st.info("티커를 입력하고 분석 버튼을 클릭하세요.")
    st.stop()

if submitted:
    ticker = normalize(ticker_input, IS_KR)
    st.session_state.update({"last_ticker":ticker,"last_period":period,"last_kr":IS_KR})
else:
    ticker = st.session_state.get("last_ticker", default_ticker)
    period = st.session_state.get("last_period","1y")
    IS_KR  = st.session_state.get("last_kr", IS_KR)

with st.spinner(f"{ticker} 데이터 수집 중..."):
    info = get_stock_info(ticker)
    hist = get_price_history(ticker, period=period)

if "error" in info or hist.empty:
    st.error(f"'{ticker}' 데이터를 불러올 수 없습니다.")
    st.stop()

hist = add_technical_indicators(hist)
fx   = get_usd_krw()

name       = info.get("longName") or info.get("shortName") or ticker
curr_raw   = info.get("currentPrice") or info.get("regularMarketPrice")
if IS_KR and not curr_raw and not hist.empty:
    curr_raw = float(hist["Close"].iloc[-1])
prev_close = info.get("previousClose")
market_cap = info.get("marketCap")

try:    current = float(curr_raw)
except: current = None

st.markdown(f"<h3>{name} <span style='color:#888;font-size:1rem;font-weight:400;'>({ticker})</span></h3>",
            unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6 = st.columns(6)
try:
    delta = f"{(current-float(prev_close))/float(prev_close)*100:+.2f}%" if prev_close else None
    if IS_KR:
        k1.metric("현재가(KRW)", f"₩{current:,.0f}", delta)
        k1.caption(f"≈ ${current/fx:,.2f}")
    else:
        k1.metric("현재가(USD)", f"${current:,.2f}", delta)
        k1.caption(f"≈ ₩{current*fx:,.0f}")
except:
    k1.metric("현재가", str(curr_raw))

try:
    if IS_KR:
        k2.metric("시가총액", f"₩{market_cap/1e12:.1f}조" if market_cap else "N/A")
    else:
        k2.metric("시가총액", format_large_number(market_cap))
except:
    k2.metric("시가총액","N/A")

k3.metric("섹터", info.get("sector","N/A")); k3.caption(info.get("industry",""))
try:    k4.metric("PER(TTM)", f"{float(info.get('trailingPE',0)):.1f}x" if info.get('trailingPE') else "N/A")
except: k4.metric("PER","N/A")
try:    k5.metric("ROE", f"{float(info.get('returnOnEquity',0))*100:.1f}%" if info.get('returnOnEquity') else "N/A")
except: k5.metric("ROE","N/A")
try:
    tp = float(info.get("targetMeanPrice",0))
    up = (tp-current)/current*100 if tp and current else None
    k6.metric("목표주가", f"₩{tp:,.0f}" if IS_KR else f"${tp:,.2f}", f"{up:+.1f}%" if up else None)
except: k6.metric("목표주가","N/A")

# 국내 추가 지표
if IS_KR and not hist.empty:
    st.markdown("---")
    kr1,kr2,kr3,kr4 = st.columns(4)
    try:
        h52 = float(hist["Close"].max())
        l52 = float(hist["Close"].min())
        d52 = (current-h52)/h52*100 if current else None
        vol_r = float(hist["Volume"].iloc[-1]) / float(hist["Volume"].rolling(20).mean().iloc[-1])
        delta_r = hist["Close"].diff()
        rsi_val = float((100-100/(1+(delta_r.clip(lower=0).rolling(14).mean()/
                  (-delta_r.clip(upper=0)).rolling(14).mean().replace(0,nan)))).iloc[-1])
        kr1.metric("52주 고점 대비", f"{d52:+.1f}%", f"₩{h52:,.0f}")
        kr2.metric("52주 저점 대비", f"{(current-l52)/l52*100:+.1f}%↑", f"₩{l52:,.0f}")
        kr3.metric("RSI(14)", f"{rsi_val:.1f}",
                   "🔴과매도" if rsi_val<30 else ("🟡과매수" if rsi_val>70 else "🟢중립"))
        kr4.metric("거래량 배율", f"{vol_r:.1f}x", "급등" if vol_r>=2 else None)
    except: pass

# ── 탭
price_change_1y = None
try:
    if len(hist)>=2:
        price_change_1y = (hist["Close"].iloc[-1]-hist["Close"].iloc[0])/hist["Close"].iloc[0]*100
except: pass

tab_chart, tab_finance, tab_ai = st.tabs(["📊 차트","📋 재무지표","🤖 AI 분석"])

with tab_chart:
    has_bb  = "BB_upper" in hist.columns
    has_rsi = "RSI" in hist.columns
    has_mac = "MACD" in hist.columns
    n_rows  = 1+(1 if has_rsi else 0)+(1 if has_mac else 0)
    heights = [0.55]+([0.2] if has_rsi else [])+([0.25] if has_mac else [])
    titles  = [f"{ticker}주가"]+([" RSI(14)"] if has_rsi else [])+([" MACD"] if has_mac else [])
    fig = make_subplots(rows=n_rows,cols=1,shared_xaxes=True,
                        row_heights=heights,vertical_spacing=0.04,subplot_titles=titles)
    fig.add_trace(go.Candlestick(x=hist.index,open=hist["Open"],high=hist["High"],
        low=hist["Low"],close=hist["Close"],name="주가",
        increasing_line_color="#ef4444",decreasing_line_color="#3b82f6"),row=1,col=1)
    if has_bb:
        for cn,dash,lb in [("BB_upper","dot","BB상단"),("BB_lower","dot","BB하단"),("BB_mid","solid","BB중선")]:
            fig.add_trace(go.Scatter(x=hist.index,y=hist[cn],name=lb,
                line=dict(color="rgba(107,114,128,0.5)",dash=dash,width=1)),row=1,col=1)
    r=2
    if has_rsi:
        fig.add_trace(go.Scatter(x=hist.index,y=hist["RSI"],name="RSI",
            line=dict(color="#8b5cf6",width=1.5)),row=r,col=1)
        fig.add_hline(y=70,line_dash="dash",line_color="red",line_width=1,row=r,col=1)
        fig.add_hline(y=30,line_dash="dash",line_color="green",line_width=1,row=r,col=1)
        r+=1
    if has_mac:
        clrs=["#ef4444" if v>=0 else "#3b82f6" for v in hist["MACD_diff"].fillna(0)]
        fig.add_trace(go.Bar(x=hist.index,y=hist["MACD_diff"],name="히스토그램",
            marker_color=clrs,opacity=0.7),row=r,col=1)
        fig.add_trace(go.Scatter(x=hist.index,y=hist["MACD"],name="MACD",
            line=dict(color="#f59e0b",width=1.5)),row=r,col=1)
        fig.add_trace(go.Scatter(x=hist.index,y=hist["MACD_signal"],name="Signal",
            line=dict(color="#64748b",width=1.5)),row=r,col=1)
    fig.update_layout(height=600,xaxis_rangeslider_visible=False,
        legend=dict(orientation="h",y=1.02),margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig,use_container_width=True)

with tab_finance:
    fc1,fc2=st.columns(2)
    with fc1:
        st.markdown("**밸류에이션**")
        for k,key in [("PER(TTM)","trailingPE"),("선행PER","forwardPE"),
                      ("PBR","priceToBook"),("PSR","priceToSalesTrailing12Months"),("EV/EBITDA","enterpriseToEbitda")]:
            v=safe_get(info,key)
            try:    st.metric(k,f"{float(v):.2f}x")
            except: st.metric(k,str(v))
    with fc2:
        st.markdown("**수익성 & 성장성**")
        for k,key in [("ROE","returnOnEquity"),("ROA","returnOnAssets"),
                      ("순이익률","profitMargins"),("매출성장률","revenueGrowth"),("EPS성장률","earningsGrowth")]:
            v=safe_get(info,key)
            try:    st.metric(k,f"{float(v)*100:.1f}%")
            except: st.metric(k,str(v))
    st.markdown("---")
    fc3,fc4=st.columns(2)
    with fc3:
        st.markdown("**재무 안정성**")
        for k,key,fmt in [("부채비율","debtToEquity",".2f"),("유동비율","currentRatio",".2f"),
                          ("배당수익률","dividendYield","pct"),("베타","beta",".2f")]:
            v=info.get(key)
            try:
                fv=float(v)
                st.metric(k,f"{fv*100:.2f}%" if fmt=="pct" else f"{fv:{fmt}}")
            except: st.metric(k,"N/A")
    with fc4:
        st.markdown("**애널리스트 의견**")
        st.metric("컨센서스",safe_get(info,"recommendationKey","N/A").upper())
        st.metric("참여 애널리스트",str(safe_get(info,"numberOfAnalystOpinions","N/A")))
        try:
            tp=float(info.get("targetMeanPrice",0)); cp=float(current)
            st.metric("평균 목표가",f"₩{tp:,.0f}" if IS_KR else f"${tp:,.2f}",
                      f"{(tp-cp)/cp*100:+.1f}%")
        except: st.metric("평균 목표가","N/A")

with tab_ai:
    st.markdown("**Claude AI 종목 분석 리포트**")
    if st.button("🤖 AI 분석 생성",type="primary"):
        with st.spinner("Claude AI 분석 중..."):
            report = analyze_stock(ticker,info,price_change_1y)
        st.markdown(report)
        st.caption("⚠️ AI 참고 자료입니다. 투자 책임은 투자자 본인에게 있습니다.")
    else:
        st.info("버튼을 클릭하면 Claude AI가 분석 리포트를 작성합니다.")
