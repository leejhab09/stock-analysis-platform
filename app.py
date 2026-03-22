"""
해외주식 투자 분석 플랫폼
AI 기반 종목 분석 · 포트폴리오 관리
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="해외주식 투자 플랫폼",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding:12px 0 8px 0;'>
            <div style='font-size:1.8rem;'>📈</div>
            <div style='font-size:1.1rem; font-weight:800; color:#1a56db;'>해외주식 플랫폼</div>
            <div style='font-size:0.75rem; color:#666; margin-top:2px;'>AI 기반 투자 분석</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        """
        <div style='font-size:0.82rem; color:#555; line-height:2.0;'>
        🏠 <b>홈</b> — 플랫폼 소개<br>
        🔍 <b>종목분석</b> — AI 분석 리포트·차트<br>
        ⚖️ <b>종목비교</b> — 최대 5개 나란히 비교<br>
        💼 <b>포트폴리오</b> — 수익률·손익 추적
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("※ 본 플랫폼은 참고용입니다.\n투자 책임은 본인에게 있습니다.")

# ── 홈 화면
st.markdown(
    """
    <div style='background: linear-gradient(135deg, #1a56db 0%, #4f86f7 100%);
                padding: 2rem 2.5rem; border-radius: 12px; margin-bottom: 2rem;'>
        <h1 style='color:white; margin:0; font-size:1.9rem;'>
            📈 해외주식 AI 투자 분석 플랫폼
        </h1>
        <p style='color:#D6E8FF; margin:0.5rem 0 0 0; font-size:1rem;'>
            Claude AI · yfinance · 실시간 데이터 기반 종목 분석 및 포트폴리오 관리
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info("### 🔍 종목 분석\n티커 입력 → 재무지표 + AI 분석 리포트 + 기술적 차트 자동 생성")
with col2:
    st.info("### ⚖️ 종목 비교\n최대 5개 종목을 나란히 비교 · AI 종합 의견")
with col3:
    st.info("### 💼 포트폴리오\n보유 종목 입력 → 수익률·손익 추적 · 원화 환산")

st.markdown("---")
st.subheader("빠른 시작 — 인기 종목")

popular = [
    ("AAPL", "Apple", "IT"),
    ("MSFT", "Microsoft", "IT"),
    ("NVDA", "NVIDIA", "반도체"),
    ("AMZN", "Amazon", "커머스"),
    ("GOOGL", "Alphabet", "IT"),
    ("TSLA", "Tesla", "전기차"),
    ("META", "Meta", "소셜"),
    ("ASML", "ASML", "반도체장비"),
]

cols = st.columns(4)
for i, (ticker, name, sector) in enumerate(popular):
    with cols[i % 4]:
        st.markdown(
            f"""<div style='border:1.5px solid #CBD5E1; border-radius:8px;
                           padding:12px; margin-bottom:10px; background:#F8FAFF;
                           text-align:center;'>
                <div style='font-size:1.1rem; font-weight:800; color:#1a56db;'>{ticker}</div>
                <div style='font-size:0.82rem; color:#333;'>{name}</div>
                <div style='font-size:0.72rem; color:#888; margin-top:2px;'>{sector}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("---")
st.caption("데이터 출처: Yahoo Finance (yfinance) · AI 분석: Claude Sonnet (Anthropic)")
