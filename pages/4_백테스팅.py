"""
pages/4_백테스팅.py — Strategy Backtesting & Statistics Report
승률, 샤프비율, MDD, 누적수익, 거래 테이블
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.quant_engine import (
    UNIVERSE, TICKER_NAMES, CHART_THEME,
    fetch_ohlcv, get_signals, run_backtest, STRATEGY_INFO,
)

st.set_page_config(page_title="백테스팅", page_icon="📉", layout="wide")
st.title("📉 전략 백테스팅")
st.markdown("Multi-Factor Mean Reversion 전략의 과거 성과를 검증합니다.")
st.markdown("---")

# ─── Controls ────────────────────────────────
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    group_sel  = st.selectbox("그룹", list(UNIVERSE.keys()))
    ticker_sel = st.selectbox("종목", UNIVERSE[group_sel])
with c2:
    period = st.selectbox("백테스트 기간", ["1y", "2y", "3y", "5y"], index=1)
with c3:
    hold_days = st.number_input("보유 기간 (거래일)", min_value=1, max_value=60, value=10)
with c4:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    st.markdown("&nbsp;", unsafe_allow_html=True)
    run_btn = st.button("▶ 백테스트 실행", type="primary", use_container_width=True)

# Direct ticker input
with st.expander("🔎 직접 티커 입력"):
    manual_ticker = st.text_input("티커 심볼", "").strip().upper()
    if manual_ticker:
        ticker_sel = manual_ticker

if not run_btn:
    st.info("종목과 기간을 선택하고 **▶ 백테스트 실행** 버튼을 누르세요.")

    with st.expander("📖 전략 설명 보기"):
        st.markdown(STRATEGY_INFO["description"])
    st.stop()

# ─── Data & Backtest ─────────────────────────
with st.spinner(f"{ticker_sel} 백테스트 실행 중..."):
    df = fetch_ohlcv(ticker_sel, period=period)
    if df.empty:
        st.error(f"{ticker_sel} 데이터를 가져올 수 없습니다.")
        st.stop()

    df = get_signals(df)
    if 'buy_sig' not in df.columns:
        st.error("지표 계산 실패 — 데이터가 부족합니다.")
        st.stop()

    result = run_backtest(df, hold_days=hold_days)

if result is None:
    st.warning(f"**{ticker_sel}** — 선택 기간 내 매수 신호(3중 합치)가 없습니다.")
    st.info("기간을 늘리거나 다른 종목을 시도해보세요.")
    st.stop()

# ─── Performance Metrics ─────────────────────
st.subheader(f"📊 성과 지표 — {ticker_sel} ({period}, 보유 {hold_days}일)")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("총 거래 수",    f"{result['count']}회")
m2.metric("승률",          f"{result['win_rate']:.1f}%",
          "양호" if result['win_rate'] > 50 else "주의")
m3.metric("평균 수익률",   f"{result['avg_ret']:+.2f}%",
          delta_color="normal" if result['avg_ret'] >= 0 else "inverse")
m4.metric("샤프 비율",     f"{result['sharpe']:.2f}",
          "양호" if result['sharpe'] > 0.5 else "낮음")
m5.metric("최대 손실(MDD)", f"{result['mdd']:.2f}%",
          delta_color="inverse")
m6.metric("최고 수익",     f"{result['best']:+.2f}%")

# ─── Verdict ─────────────────────────────────
st.markdown("---")
score = 0
score += 1 if result['win_rate'] > 50 else 0
score += 1 if result['avg_ret'] > 0 else 0
score += 1 if result['sharpe'] > 0.5 else 0
score += 1 if abs(result['mdd']) < 10 else 0

verdict_map = {
    4: ("✅ 우수 전략", "success", "샤프·승률·MDD 모두 양호. 실제 매매 적용 고려 가능."),
    3: ("🟡 보통 전략", "warning", "대부분 지표 양호하나 일부 개선 필요."),
    2: ("🟠 주의 필요", "warning", "리스크 관리 강화 후 적용 권고."),
    1: ("🔴 재검토 필요", "error",  "전략 파라미터 조정 또는 종목 재선택 권고."),
    0: ("🔴 부적합",     "error",  "해당 종목에 전략이 맞지 않습니다."),
}
verdict_title, verdict_type, verdict_desc = verdict_map.get(score, verdict_map[0])

getattr(st, verdict_type)(f"**{verdict_title}** (점수: {score}/4) — {verdict_desc}")

st.markdown("---")

# ─── Charts ──────────────────────────────────
tab_cumret, tab_dist, tab_chart = st.tabs(["📈 누적 수익", "📊 수익 분포", "📉 가격 + 신호"])

trades_df = pd.DataFrame(result['trades'])
trades_df['date'] = pd.to_datetime(trades_df['date'])

# ── Cumulative Returns ────────────────────────
with tab_cumret:
    fig_cum = go.Figure()
    cum_rets = np.cumsum([t['ret'] for t in result['trades']])
    colors = ['#00CC66' if v >= 0 else '#FF4444' for v in cum_rets]

    fig_cum.add_trace(go.Scatter(
        x=list(range(1, len(cum_rets)+1)),
        y=cum_rets,
        mode='lines+markers',
        name='누적 수익률',
        line=dict(color="#3498DB", width=2),
        marker=dict(color=colors, size=8),
        fill='tozeroy',
        fillcolor='rgba(96,165,250,0.1)',
    ))
    fig_cum.add_hline(y=0, line_dash="dash", line_color="#888")
    fig_cum.update_layout(
        title="누적 수익률 (%)",
        height=400,
        xaxis_title="거래 번호",
        yaxis_title="누적 수익률 (%)",
        plot_bgcolor="#FAFAFA", paper_bgcolor="#FFFFFF",
        font_color="#333333",
        xaxis=dict(gridcolor="#E8E8E8"),
        yaxis=dict(gridcolor="#E8E8E8"),
    )
    st.plotly_chart(fig_cum, use_container_width=True)

# ── Return Distribution ───────────────────────
with tab_dist:
    rets = [t['ret'] for t in result['trades']]
    bar_colors = ['#00CC66' if r >= 0 else '#FF4444' for r in rets]
    fig_dist = make_subplots(rows=1, cols=2,
                              subplot_titles=["거래별 수익률", "수익률 히스토그램"])

    fig_dist.add_trace(go.Bar(
        x=list(range(1, len(rets)+1)), y=rets,
        marker_color=bar_colors, name="수익률",
    ), row=1, col=1)
    fig_dist.add_hline(y=0, line_dash="dash", line_color="#888", row=1, col=1)

    fig_dist.add_trace(go.Histogram(
        x=rets, nbinsx=15,
        marker_color="#3498DB", opacity=0.7, name="분포",
    ), row=1, col=2)
    fig_dist.add_vline(x=0, line_dash="dash", line_color="#888", row=1, col=2)

    fig_dist.update_layout(
        height=400, showlegend=False,
        plot_bgcolor="#FAFAFA", paper_bgcolor="#FFFFFF",
        font_color="#333333",
    )
    for r in [1]:
        for c in [1, 2]:
            fig_dist.update_xaxes(gridcolor="#E8E8E8", row=r, col=c)
            fig_dist.update_yaxes(gridcolor="#E8E8E8", row=r, col=c)

    st.plotly_chart(fig_dist, use_container_width=True)

# ── Price Chart with Signals ──────────────────
with tab_chart:
    df_sig = get_signals(fetch_ohlcv(ticker_sel, period=period))
    if not df_sig.empty and 'buy_sig' in df_sig.columns:
        sig_pts = df_sig[df_sig['buy_sig'] == True]
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(
            x=df_sig.index, y=df_sig['Close'],
            mode='lines', name='Close',
            line=dict(color="#3498DB", width=1.5),
        ))
        if 'bb_l' in df_sig.columns:
            fig_p.add_trace(go.Scatter(
                x=df_sig.index, y=df_sig['bb_l'],
                mode='lines', name='BB Lower',
                line=dict(color='rgba(100,149,237,0.5)', width=1, dash='dot'),
            ))
            fig_p.add_trace(go.Scatter(
                x=df_sig.index, y=df_sig['bb_u'],
                mode='lines', name='BB Upper',
                line=dict(color='rgba(100,149,237,0.5)', width=1, dash='dot'),
            ))
        if not sig_pts.empty:
            fig_p.add_trace(go.Scatter(
                x=sig_pts.index,
                y=sig_pts['Close'] * 0.99,
                mode='markers',
                name='매수 신호',
                marker=dict(symbol='triangle-up', color='#FFD700', size=14,
                            line=dict(color='#FF8800', width=1)),
            ))
        fig_p.update_layout(
            title=f"{ticker_sel} 가격 + 매수 신호",
            height=400,
            plot_bgcolor="#FAFAFA", paper_bgcolor="#FFFFFF",
            font_color="#333333",
            xaxis=dict(gridcolor="#E8E8E8"),
            yaxis=dict(gridcolor="#E8E8E8"),
        )
        st.plotly_chart(fig_p, use_container_width=True)

# ─── Trade Table ─────────────────────────────
st.markdown("---")
st.subheader("📋 거래 내역")

trades_display = trades_df.copy()
trades_display['수익률'] = trades_display['ret'].apply(lambda x: f"{x:+.2f}%")
trades_display['결과'] = trades_display['ret'].apply(
    lambda x: "✅ 수익" if x > 0 else "❌ 손실"
)
if 'rsi' in trades_display.columns:
    trades_display['RSI'] = trades_display['rsi'].apply(
        lambda x: f"{x:.1f}" if x else "-"
    )
if 'mfi' in trades_display.columns:
    trades_display['MFI'] = trades_display['mfi'].apply(
        lambda x: f"{x:.1f}" if x else "-"
    )

show_cols = ['date', 'buy', 'sell', '수익률', '결과']
if 'RSI' in trades_display.columns:
    show_cols += ['RSI']
if 'MFI' in trades_display.columns:
    show_cols += ['MFI']

trades_display = trades_display[show_cols].rename(columns={
    'date': '신호 날짜', 'buy': '매수가', 'sell': '매도가'
})
trades_display = trades_display.sort_values('신호 날짜', ascending=False)

def color_result(val):
    if '✅' in str(val):
        return 'color:#00CC66;font-weight:bold'
    elif '❌' in str(val):
        return 'color:#FF4444;font-weight:bold'
    return ''

styled_trades = trades_display.style.applymap(color_result, subset=['결과']).format({
    '매수가': '{:.2f}', '매도가': '{:.2f}',
})
st.dataframe(styled_trades, use_container_width=True, hide_index=True)

st.markdown("---")
with st.expander("📖 전략 설명"):
    st.markdown(STRATEGY_INFO["description"])

st.caption(f"백테스트: {ticker_sel} · {period} · 보유 {hold_days}거래일 · 데이터: Yahoo Finance")
