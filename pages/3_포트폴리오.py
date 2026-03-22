"""
포트폴리오 관리 페이지
보유 종목 입력 → 수익률·손익 추적 · 원화 환산
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json

from utils.stock_data import get_stock_info, get_usd_krw, format_large_number

st.set_page_config(page_title="포트폴리오 | 해외주식", layout="wide")

st.markdown("<h2 style='color:#1a56db;margin-bottom:4px;'>💼 포트폴리오 관리</h2>", unsafe_allow_html=True)
st.markdown("<p style='color:#666;font-size:.85rem;margin-bottom:16px;'>보유 종목을 입력하면 수익률과 손익을 실시간으로 계산합니다.</p>", unsafe_allow_html=True)

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "portfolio.json")

def load_portfolio() -> list:
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_portfolio(holdings: list):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)

# 초기화
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = load_portfolio()

portfolio = st.session_state["portfolio"]

# ── 사이드바 — 종목 추가
with st.sidebar:
    st.markdown("### ➕ 보유 종목 추가")
    with st.form("add_form"):
        new_ticker = st.text_input("티커", placeholder="AAPL").upper().strip()
        new_qty = st.number_input("수량 (주)", min_value=0.001, value=1.0, step=1.0)
        new_price = st.number_input("매수가 (USD)", min_value=0.01, value=100.0, step=0.01)
        new_memo = st.text_input("메모 (선택)", placeholder="예: 장기보유")
        add_btn = st.form_submit_button("추가", use_container_width=True, type="primary")

    if add_btn and new_ticker:
        portfolio.append({
            "ticker": new_ticker,
            "qty": new_qty,
            "avg_price": new_price,
            "memo": new_memo,
        })
        save_portfolio(portfolio)
        st.session_state["portfolio"] = portfolio
        st.success(f"{new_ticker} 추가 완료")
        st.rerun()

    st.markdown("---")
    if st.button("💾 포트폴리오 저장", use_container_width=True):
        save_portfolio(portfolio)
        st.success("저장 완료")

    if portfolio and st.button("🗑️ 전체 초기화", use_container_width=True):
        if st.session_state.get("confirm_clear"):
            st.session_state["portfolio"] = []
            save_portfolio([])
            st.session_state.pop("confirm_clear")
            st.rerun()
        else:
            st.session_state["confirm_clear"] = True
            st.warning("한 번 더 클릭하면 삭제됩니다.")

if not portfolio:
    st.info("사이드바에서 보유 종목을 추가하세요.")
    st.stop()

# ── 현재가 조회
fx = get_usd_krw()
rows = []

with st.spinner("현재가 조회 중..."):
    for h in portfolio:
        info = get_stock_info(h["ticker"])
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        try:
            current = float(current)
        except Exception:
            current = None

        cost = h["qty"] * h["avg_price"]
        if current:
            value = h["qty"] * current
            pnl = value - cost
            pnl_pct = pnl / cost * 100
        else:
            value = pnl = pnl_pct = None

        rows.append({
            "티커": h["ticker"],
            "회사명": info.get("longName", h["ticker"]),
            "수량": h["qty"],
            "매수가": h["avg_price"],
            "현재가": current,
            "평가금액_USD": value,
            "손익_USD": pnl,
            "수익률_%": pnl_pct,
            "평가금액_KRW": value * fx if value else None,
            "메모": h.get("memo", ""),
        })

df = pd.DataFrame(rows)

# ── KPI 요약
total_cost = sum(r["수량"] * r["매수가"] for r in rows)
total_value = sum(r["평가금액_USD"] for r in rows if r["평가금액_USD"])
total_pnl = total_value - total_cost if total_value else 0
total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("총 투자금액", f"${total_cost:,.0f}", f"≈ ₩{total_cost*fx:,.0f}")
k2.metric("총 평가금액", f"${total_value:,.0f}", f"≈ ₩{total_value*fx:,.0f}")
k3.metric("총 손익", f"${total_pnl:+,.0f}", f"{total_pnl_pct:+.2f}%",
          delta_color="normal")
k4.metric("USD/KRW", f"{fx:,.1f}")

st.markdown("---")

# ── 테이블
st.markdown("### 보유 종목 현황")

def color_pnl(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #ef4444; font-weight:700"
        elif v < 0:
            return "color: #3b82f6; font-weight:700"
    except Exception:
        pass
    return ""

disp_df = df[["티커", "회사명", "수량", "매수가", "현재가", "평가금액_USD", "손익_USD", "수익률_%", "평가금액_KRW", "메모"]].copy()
disp_df["매수가"] = disp_df["매수가"].apply(lambda x: f"${x:,.2f}")
disp_df["현재가"] = disp_df["현재가"].apply(lambda x: f"${x:,.2f}" if x else "N/A")
disp_df["평가금액_USD"] = disp_df["평가금액_USD"].apply(lambda x: f"${x:,.0f}" if x else "N/A")
disp_df["평가금액_KRW"] = disp_df["평가금액_KRW"].apply(lambda x: f"₩{x:,.0f}" if x else "N/A")
disp_df["손익_USD"] = disp_df["손익_USD"].apply(lambda x: f"${x:+,.0f}" if x else "N/A")
disp_df["수익률_%"] = disp_df["수익률_%"].apply(lambda x: f"{x:+.2f}%" if x else "N/A")

try:
    styled = disp_df.style.map(color_pnl, subset=["손익_USD", "수익률_%"])
except AttributeError:
    styled = disp_df.style.applymap(color_pnl, subset=["손익_USD", "수익률_%"])

st.dataframe(styled, use_container_width=True, height=300)

# ── 종목 삭제
st.markdown("**종목 삭제**")
del_ticker = st.selectbox("삭제할 종목 선택", [h["ticker"] for h in portfolio])
if st.button(f"'{del_ticker}' 삭제", type="secondary"):
    st.session_state["portfolio"] = [h for h in portfolio if h["ticker"] != del_ticker]
    save_portfolio(st.session_state["portfolio"])
    st.rerun()

st.markdown("---")

# ── 차트
ch1, ch2 = st.columns(2)

with ch1:
    st.markdown("### 포트폴리오 비중 (평가금액 기준)")
    valid = df.dropna(subset=["평가금액_USD"])
    if not valid.empty:
        fig_pie = px.pie(valid, values="평가금액_USD", names="티커",
                         color_discrete_sequence=px.colors.qualitative.Set2)
        fig_pie.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

with ch2:
    st.markdown("### 종목별 수익률 (%)")
    valid2 = df.dropna(subset=["수익률_%"])
    if not valid2.empty:
        colors = ["#ef4444" if v >= 0 else "#3b82f6" for v in valid2["수익률_%"]]
        fig_bar = go.Figure(go.Bar(
            x=valid2["티커"], y=valid2["수익률_%"],
            marker_color=colors, text=valid2["수익률_%"].apply(lambda x: f"{x:+.1f}%"),
            textposition="outside"
        ))
        fig_bar.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=20),
                              yaxis_title="수익률 (%)", showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# ── CSV 다운로드
csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button("⬇ 포트폴리오 CSV 다운로드", csv, "portfolio.csv", "text/csv")
