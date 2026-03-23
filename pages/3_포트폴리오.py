"""
포트폴리오 관리 — 🇺🇸 미국(USD) / 🇰🇷 국내(KRW) 탭 분리
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json
import yfinance as yf

from utils.stock_data import get_stock_info, get_usd_krw, format_large_number
from utils.kr_stock_data import suffix as kr_suffix

st.set_page_config(page_title="포트폴리오", layout="wide")
st.markdown("<h2 style='color:#333;margin-bottom:4px;'>💼 포트폴리오 관리</h2>",
            unsafe_allow_html=True)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

def port_file(is_kr): return os.path.join(DATA_DIR, "kr_portfolio.json" if is_kr else "portfolio.json")
def load_port(is_kr):
    f = port_file(is_kr)
    if os.path.exists(f):
        try:
            with open(f,encoding="utf-8") as fp: return json.load(fp)
        except: pass
    return []
def save_port(holdings, is_kr):
    with open(port_file(is_kr),"w",encoding="utf-8") as fp:
        json.dump(holdings, fp, ensure_ascii=False, indent=2)

def get_current_price(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except: pass
    info = get_stock_info(ticker)
    p = info.get("currentPrice") or info.get("regularMarketPrice")
    try: return float(p)
    except: return None

def color_pnl(val):
    try:
        v = float(str(val).replace("$","").replace("₩","").replace(",","").replace("+","").replace("%",""))
        if "+" in str(val) or v > 0: return "color:#ef4444;font-weight:700"
        if v < 0: return "color:#3b82f6;font-weight:700"
    except: pass
    return ""

# ── 탭
tab_us, tab_kr = st.tabs(["🇺🇸 미국 주식 (USD)", "🇰🇷 국내 주식 (KRW)"])

for IS_KR, tab in [(False, tab_us), (True, tab_kr)]:
    with tab:
        flag  = "🇰🇷" if IS_KR else "🇺🇸"
        color = "#c0392b" if IS_KR else "#1a56db"
        bg    = "#FFF0F0" if IS_KR else "#EBF5FF"
        cur   = "KRW (₩)" if IS_KR else "USD ($)"
        st.markdown(f"<div style='background:{bg};border-left:4px solid {color};"
                    f"padding:8px 14px;border-radius:6px;margin-bottom:12px;'>"
                    f"{flag} <b style='color:{color};'>{cur} 포트폴리오</b></div>",
                    unsafe_allow_html=True)

        sess_key = "kr_portfolio" if IS_KR else "us_portfolio"
        if sess_key not in st.session_state:
            st.session_state[sess_key] = load_port(IS_KR)
        portfolio = st.session_state[sess_key]

        # 사이드바 대신 expander로 추가 폼
        with st.expander("➕ 보유 종목 추가"):
            with st.form(f"add_{'kr' if IS_KR else 'us'}"):
                c1,c2,c3,c4 = st.columns([2,1,2,2])
                with c1:
                    ph = "005930 또는 005930.KS" if IS_KR else "AAPL"
                    new_tk = st.text_input("티커", placeholder=ph).strip()
                with c2:
                    new_qty = st.number_input("수량", min_value=0.001, value=10.0 if IS_KR else 1.0, step=1.0)
                with c3:
                    lbl = "매수가 (원)" if IS_KR else "매수가 (USD)"
                    new_price = st.number_input(lbl, min_value=0.01, value=70000.0 if IS_KR else 100.0)
                with c4:
                    new_memo = st.text_input("메모", placeholder="예: 장기보유")
                if st.form_submit_button("추가", type="primary"):
                    tk = kr_suffix(new_tk.upper()) if IS_KR else new_tk.upper()
                    portfolio.append({"ticker":tk,"qty":new_qty,"avg_price":new_price,"memo":new_memo})
                    save_port(portfolio, IS_KR)
                    st.session_state[sess_key] = portfolio
                    st.success(f"{tk} 추가 완료")
                    st.rerun()

        if not portfolio:
            st.info("보유 종목을 추가하세요.")
            continue

        fx = get_usd_krw()

        # 현재가 조회
        rows = []
        with st.spinner("현재가 조회 중..."):
            for h in portfolio:
                curr = get_current_price(h["ticker"])
                cost = h["qty"] * h["avg_price"]
                if curr:
                    value  = h["qty"] * curr
                    pnl    = value - cost
                    pnl_pct= pnl / cost * 100
                else:
                    value = pnl = pnl_pct = None
                info = get_stock_info(h["ticker"])
                rows.append({
                    "티커":    h["ticker"].replace(".KS","").replace(".KQ",""),
                    "종목명":  info.get("shortName") or info.get("longName") or h["ticker"],
                    "수량":    h["qty"],
                    "매수가":  h["avg_price"],
                    "현재가":  curr,
                    "평가금액": value,
                    "손익":    pnl,
                    "수익률%": pnl_pct,
                    "메모":    h.get("memo",""),
                })
        df = pd.DataFrame(rows)

        # KPI
        total_cost  = sum(r["수량"]*r["매수가"] for r in rows)
        total_value = sum(r["평가금액"] for r in rows if r["평가금액"])
        total_pnl   = total_value - total_cost if total_value else 0
        total_pct   = total_pnl / total_cost * 100 if total_cost else 0

        k1,k2,k3,k4 = st.columns(4)
        if IS_KR:
            k1.metric("총 투자금",  f"₩{total_cost:,.0f}",  f"≈ ${total_cost/fx:,.0f}")
            k2.metric("총 평가금액",f"₩{total_value:,.0f}", f"≈ ${total_value/fx:,.0f}")
        else:
            k1.metric("총 투자금",  f"${total_cost:,.0f}",  f"≈ ₩{total_cost*fx:,.0f}")
            k2.metric("총 평가금액",f"${total_value:,.0f}", f"≈ ₩{total_value*fx:,.0f}")
        k3.metric("총 손익",
                  f"₩{total_pnl:+,.0f}" if IS_KR else f"${total_pnl:+,.0f}",
                  f"{total_pct:+.2f}%")
        k4.metric("USD/KRW", f"{fx:,.1f}")

        st.markdown("---")

        # 테이블
        st.markdown("#### 보유 종목 현황")
        sym = "₩" if IS_KR else "$"
        disp = df.copy()
        disp["매수가"]   = disp["매수가"].apply(lambda x: f"{sym}{x:,.0f}" if IS_KR else f"{sym}{x:,.2f}")
        disp["현재가"]   = disp["현재가"].apply(lambda x: f"{sym}{x:,.0f}" if (x and IS_KR) else (f"{sym}{x:,.2f}" if x else "N/A"))
        disp["평가금액"] = disp["평가금액"].apply(lambda x: f"{sym}{x:,.0f}" if x else "N/A")
        disp["손익"]     = disp["손익"].apply(lambda x: f"{sym}{x:+,.0f}" if x else "N/A")
        disp["수익률%"]  = disp["수익률%"].apply(lambda x: f"{x:+.2f}%" if x else "N/A")

        try:    styled = disp.style.map(color_pnl, subset=["손익","수익률%"])
        except: styled = disp.style.applymap(color_pnl, subset=["손익","수익률%"])
        st.dataframe(styled, use_container_width=True, height=300)

        # 삭제
        del_tk = st.selectbox("삭제할 종목", [h["ticker"] for h in portfolio],
                              key=f"del_{'kr' if IS_KR else 'us'}")
        if st.button(f"'{del_tk}' 삭제", type="secondary", key=f"del_btn_{'kr' if IS_KR else 'us'}"):
            st.session_state[sess_key] = [h for h in portfolio if h["ticker"] != del_tk]
            save_port(st.session_state[sess_key], IS_KR)
            st.rerun()

        st.markdown("---")

        # 차트
        ch1,ch2 = st.columns(2)
        with ch1:
            st.markdown("#### 포트폴리오 비중")
            valid = df.dropna(subset=["평가금액"])
            if not valid.empty:
                fig_pie = px.pie(valid, values="평가금액", names="티커",
                                 color_discrete_sequence=px.colors.qualitative.Set2 if not IS_KR
                                 else px.colors.sequential.Reds_r)
                fig_pie.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
        with ch2:
            st.markdown("#### 종목별 수익률")
            valid2 = df.dropna(subset=["수익률%"])
            if not valid2.empty:
                bar_colors = ["#ef4444" if v>=0 else "#3b82f6" for v in valid2["수익률%"]]
                fig_bar = go.Figure(go.Bar(
                    x=valid2["티커"], y=valid2["수익률%"], marker_color=bar_colors,
                    text=valid2["수익률%"].apply(lambda x: f"{x:+.1f}%"), textposition="outside"
                ))
                fig_bar.add_hline(y=0, line_color="gray")
                fig_bar.update_layout(height=300, yaxis_title="수익률(%)", showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

        # 저장 & CSV
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("💾 저장", use_container_width=True, key=f"save_{'kr' if IS_KR else 'us'}"):
                save_port(portfolio, IS_KR)
                st.success("저장 완료")
        with col_b:
            csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            fname = "kr_portfolio.csv" if IS_KR else "us_portfolio.csv"
            st.download_button("⬇ CSV", csv, fname, "text/csv",
                               use_container_width=True,
                               key=f"csv_{'kr' if IS_KR else 'us'}")
