"""
app.py — Stock Analysis Platform · Home Dashboard
"""

import streamlit as st
from utils.quant_engine import get_vix, fetch_index_prices, UNIVERSE, STRATEGY_INFO

st.set_page_config(
    page_title="Stock Analysis Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar ────────────────────────────────
st.sidebar.title("📈 Stock Analysis Platform")
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 페이지 안내
| 페이지 | 내용 |
|--------|------|
| 🏠 홈 | 대시보드 요약 |
| 🌡️ 시장체력 | VIX + 지수 현황 |
| 🔍 스캐너 | 신호 스캔 |
| 📊 전략시각화 | 차트 분석 |
| 📉 백테스팅 | 전략 검증 |
""")

# ─── Title ──────────────────────────────────
st.title("📈 Stock Analysis Platform")
st.markdown("**Multi-Factor Mean Reversion Strategy** · Freqtrade-inspired framework")
st.markdown("---")

# ─── VIX + Market Overview ──────────────────
col_vix, col_sp, col_nq, col_dw, col_ks = st.columns(5)

vix, regime, regime_color = get_vix()
with col_vix:
    if vix:
        st.metric("🌡️ VIX", f"{vix:.2f}", help="CBOE Volatility Index")
        st.markdown(f"<span style='color:{regime_color};font-weight:bold'>{regime}</span>",
                    unsafe_allow_html=True)
    else:
        st.metric("🌡️ VIX", "N/A")

indices = fetch_index_prices()
cols = [col_sp, col_nq, col_dw, col_ks]
names = ["S&P 500", "NASDAQ", "DOW", "KOSPI"]
for col, name in zip(cols, names):
    with col:
        if name in indices:
            d = indices[name]
            delta_str = f"{d['change_pct']:+.2f}%"
            st.metric(name, f"{d['price']:,.2f}", delta_str)
        else:
            st.metric(name, "N/A")

st.markdown("---")

# ─── Strategy Summary ───────────────────────
st.subheader("🧠 전략 요약")

c1, c2, c3 = st.columns(3)
with c1:
    st.info("""
**📐 진입 조건 (3중 합치)**
- RSI(14) < 35 ← 과매도
- MFI(14) < 35 ← 자금 이탈
- Close ≤ BB Lower(20, 2σ) ← 통계 하단
""")
with c2:
    st.warning("""
**📤 청산 조건**
- 진입 후 10 거래일 경과 후 청산
- (확장 예정) RSI > 65 조기 청산
- (확장 예정) BB 상단 도달 청산
""")
with c3:
    st.success("""
**🌡️ VIX 레짐 필터**
- VIX < 20 → 공격적 매매
- VIX 20~30 → 신중 (축소)
- VIX ≥ 30 → 현금 보유
""")

# ─── Universe Overview ──────────────────────
st.markdown("---")
st.subheader("🌐 스캔 유니버스")

ucols = st.columns(4)
for i, (group, tickers) in enumerate(UNIVERSE.items()):
    with ucols[i]:
        st.markdown(f"**{group}** ({len(tickers)}개)")
        st.markdown("\n".join([f"- `{t}`" for t in tickers[:8]]))
        if len(tickers) > 8:
            st.markdown(f"_... 외 {len(tickers)-8}개_")

# ─── Navigation Guide ───────────────────────
st.markdown("---")
st.subheader("🗺️ 분석 플로우")

flow_cols = st.columns(4)
pages = [
    ("🌡️ 시장체력",   "VIX 레짐 확인 후\n매매 가능 여부 판단"),
    ("🔍 스캐너",     "전체 유니버스 스캔\n신호 종목 발굴"),
    ("📊 전략시각화", "개별 종목 차트\n진입 시점 확인"),
    ("📉 백테스팅",   "전략 성과 검증\n통계 리포트"),
]
for col, (title, desc) in zip(flow_cols, pages):
    with col:
        st.markdown(f"### {title}")
        st.caption(desc)

st.markdown("---")
st.caption("v1.0 · Multi-Factor Mean Reversion · Freqtrade-inspired")
