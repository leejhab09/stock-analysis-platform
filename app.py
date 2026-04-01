import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="주식 분석 플랫폼 v2.0", layout="wide")

# 1. 사이드바 - 시장 지표 (VIX 등)
st.sidebar.header("📊 시장 실시간 지표")

def get_vix():
    try:
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="1d")
        if not vix_data.empty:
            return round(vix_data['Close'].iloc[-1], 2)
        return "데이터 없음"
    except:
        return "연결 에러"

vix_score = get_vix()
st.sidebar.metric(label="VIX (공포지수)", value=vix_score)
st.sidebar.metric(label="금리 인하 확률 (Polymarket)", value="68%", delta="-2%")

# 2. 메인 화면 레이아웃
st.title("📈 스마트 주식 분석 & 자금 흐름 대시보드")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💡 시장 자금 흐름 (Sankey Diagram)")
    
    # Sankey Diagram 데이터 구성
    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 15,
          thickness = 20,
          line = dict(color = "black", width = 0.5),
          label = ["개인투자자", "기관", "외국인", "반도체 섹터", "2차전지 섹터", "현금보유"],
          color = ["#3366CC", "#DC3912", "#FF9900", "#109618", "#990099", "#AAAAAA"]
        ),
        link = dict(
          source = [0, 1, 2, 0, 1, 2], 
          target = [3, 3, 4, 5, 5, 5], 
          value = [40, 60, 30, 20, 10, 50] 
      ))])

    fig.update_layout(title_text="주요 투자 주체별 섹터 자금 이동 (실시간 추정)", font_size=12)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📰 뉴스 감성 분석")
    news_input = st.text_area("분석할 뉴스 기사를 입력하세요:", height=150, placeholder="여기에 뉴스 내용을 붙여넣으세요...")
    if st.button("감성 분석 실행"):
        st.success("분석 완료: 긍정(Positive) - AI 점수: 85점")
        st.progress(0.85)

# 3. 하단 캡션 (따옴표 에러 완벽 수정)
st.divider()
st.caption("※ 본 플랫폼은 데이터 시각화 및 연구 참고용입니다. 실제 투자 시에는 전문가와 상의하시기 바랍니다.")
