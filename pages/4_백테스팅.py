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
_groups = list(UNIVERSE.keys())
_period_opts = ["3mo", "6mo", "1y", "2y", "3y", "5y"]
if "shared_group" not in st.session_state:
    st.session_state["shared_group"] = _groups[0]
if "shared_ticker" not in st.session_state:
    st.session_state["shared_ticker"] = UNIVERSE[_groups[0]][0]
if "shared_period" not in st.session_state:
    st.session_state["shared_period"] = "1y"
if "shared_hold_days" not in st.session_state:
    st.session_state["shared_hold_days"] = 10

c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    _g_idx = _groups.index(st.session_state["shared_group"]) if st.session_state["shared_group"] in _groups else 0
    group_sel = st.selectbox("그룹", _groups, index=_g_idx)
    st.session_state["shared_group"] = group_sel
    tickers_in_group = UNIVERSE[group_sel]
    curr_ticker = st.session_state["shared_ticker"]
    if curr_ticker not in tickers_in_group:
        curr_ticker = tickers_in_group[0]
    curr_idx = tickers_in_group.index(curr_ticker)
    display_options = [f"{t} — {TICKER_NAMES.get(t, t)}" for t in tickers_in_group]
    sel_idx = st.selectbox("종목", range(len(tickers_in_group)),
                           format_func=lambda i: display_options[i],
                           index=curr_idx)
    ticker_sel = tickers_in_group[sel_idx]
    st.session_state["shared_ticker"] = ticker_sel
with c2:
    _p_idx = _period_opts.index(st.session_state["shared_period"]) if st.session_state["shared_period"] in _period_opts else 2
    period = st.selectbox("백테스트 기간", _period_opts, index=_p_idx)
    st.session_state["shared_period"] = period
with c3:
    hold_days = st.number_input("보유 기간 (거래일)", min_value=1, max_value=60, value=st.session_state["shared_hold_days"])
    st.session_state["shared_hold_days"] = int(hold_days)
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

# ─── Section A: 그룹 전체 백테스팅 ──────────────
st.markdown("---")
with st.expander("📊 그룹 전체 백테스팅", expanded=False):
    st.markdown(f"**{group_sel}** 그룹의 모든 종목에 동일 전략을 적용하여 성과를 비교합니다.")
    group_bt_btn = st.button("▶ 그룹 전체 실행", key="group_bt_btn")

    if group_bt_btn:
        group_tickers = UNIVERSE[group_sel]
        group_rows = []

        with st.spinner(f"{group_sel} 그룹 전체 백테스팅 중... ({len(group_tickers)}개 종목)"):
            for tkr in group_tickers:
                tkr_name = TICKER_NAMES.get(tkr, tkr)
                try:
                    tkr_df = fetch_ohlcv(tkr, period=period)
                    if tkr_df.empty:
                        group_rows.append({
                            "종목": tkr, "이름": tkr_name,
                            "거래수": "신호없음", "승률(%)": None,
                            "평균수익(%)": None, "샤프": None,
                            "MDD(%)": None, "최고수익(%)": None,
                        })
                        continue
                    tkr_df = get_signals(tkr_df)
                    if 'buy_sig' not in tkr_df.columns:
                        group_rows.append({
                            "종목": tkr, "이름": tkr_name,
                            "거래수": "신호없음", "승률(%)": None,
                            "평균수익(%)": None, "샤프": None,
                            "MDD(%)": None, "최고수익(%)": None,
                        })
                        continue
                    tkr_result = run_backtest(tkr_df, hold_days=hold_days)
                    if tkr_result is None:
                        group_rows.append({
                            "종목": tkr, "이름": tkr_name,
                            "거래수": "신호없음", "승률(%)": None,
                            "평균수익(%)": None, "샤프": None,
                            "MDD(%)": None, "최고수익(%)": None,
                        })
                    else:
                        group_rows.append({
                            "종목": tkr,
                            "이름": tkr_name,
                            "거래수": tkr_result["count"],
                            "승률(%)": round(tkr_result["win_rate"], 1),
                            "평균수익(%)": round(tkr_result["avg_ret"], 2),
                            "샤프": round(tkr_result["sharpe"], 2),
                            "MDD(%)": round(tkr_result["mdd"], 2),
                            "최고수익(%)": round(tkr_result["best"], 2),
                        })
                except Exception:
                    group_rows.append({
                        "종목": tkr, "이름": tkr_name,
                        "거래수": "오류", "승률(%)": None,
                        "평균수익(%)": None, "샤프": None,
                        "MDD(%)": None, "최고수익(%)": None,
                    })

        group_df = pd.DataFrame(group_rows)

        # Separate valid and no-signal rows
        valid_mask = group_df["승률(%)"].notna()
        valid_df = group_df[valid_mask].sort_values("승률(%)", ascending=False)
        invalid_df = group_df[~valid_mask]
        sorted_df = pd.concat([valid_df, invalid_df], ignore_index=True)

        def _color_group_row(row):
            if row["승률(%)"] is None:
                return [""] * len(row)
            if row["승률(%)"] > 55:
                color = "color:#00CC66;font-weight:bold"
            elif row["승률(%)"] < 45:
                color = "color:#FF4444;font-weight:bold"
            else:
                color = ""
            return [color if col == "승률(%)" else "" for col in row.index]

        # Fill None with "신호없음" for display in string columns
        display_df = sorted_df.copy()
        for col in ["거래수", "승률(%)", "평균수익(%)", "샤프", "MDD(%)", "최고수익(%)"]:
            display_df[col] = display_df[col].apply(
                lambda v: "신호없음" if v is None else v
            )

        styled_group = display_df.style.apply(_color_group_row, axis=1)
        st.dataframe(styled_group, use_container_width=True, hide_index=True)

        n_valid = valid_mask.sum()
        n_total = len(group_rows)
        st.caption(
            f"총 {n_total}개 종목 중 {n_valid}개 신호 발생 · "
            f"기간: {period} · 보유: {hold_days}거래일"
        )

# ─── Section B: Walk-Forward 검증 ───────────────
st.markdown("---")
with st.expander("🔄 Walk-Forward 검증", expanded=False):
    st.markdown(
        "전체 데이터를 In-Sample(학습)과 Out-of-Sample(검증)으로 분할하여 "
        "과적합 여부를 확인합니다."
    )
    wf_split = st.slider(
        "In-Sample 비율 (%)", min_value=50, max_value=80,
        value=70, step=5, key="wf_split"
    )
    wf_btn = st.button("▶ Walk-Forward 실행", key="wf_btn")

    if wf_btn:
        with st.spinner(f"{ticker_sel} Walk-Forward 검증 중..."):
            wf_df = fetch_ohlcv(ticker_sel, period=period)
            if wf_df.empty:
                st.error(f"{ticker_sel} 데이터를 가져올 수 없습니다.")
            else:
                wf_df = get_signals(wf_df)
                if 'buy_sig' not in wf_df.columns:
                    st.error("지표 계산 실패 — 데이터가 부족합니다.")
                else:
                    split_idx = int(len(wf_df) * wf_split / 100)
                    in_sample_df  = wf_df.iloc[:split_idx]
                    out_sample_df = wf_df.iloc[split_idx:]

                    in_result  = run_backtest(in_sample_df,  hold_days=hold_days)
                    out_result = run_backtest(out_sample_df, hold_days=hold_days)

                    col_in, col_out = st.columns(2)

                    with col_in:
                        st.markdown("### 📚 In-Sample (학습)")
                        st.caption(
                            f"기간: {wf_df.index[0].date()} ~ "
                            f"{wf_df.index[split_idx - 1].date()} "
                            f"({wf_split}%)"
                        )
                        if in_result is None:
                            st.warning("In-Sample 구간에 매수 신호가 없습니다.")
                        else:
                            st.metric("거래수",   f"{in_result['count']}회")
                            st.metric("승률",     f"{in_result['win_rate']:.1f}%")
                            st.metric("평균수익", f"{in_result['avg_ret']:+.2f}%")
                            st.metric("샤프",     f"{in_result['sharpe']:.2f}")
                            st.metric("MDD",      f"{in_result['mdd']:.2f}%")

                    with col_out:
                        st.markdown("### 🔮 Out-of-Sample (검증)")
                        st.caption(
                            f"기간: {wf_df.index[split_idx].date()} ~ "
                            f"{wf_df.index[-1].date()} "
                            f"({100 - wf_split}%)"
                        )
                        if out_result is None:
                            st.warning("Out-of-Sample 구간에 매수 신호가 없습니다.")
                        else:
                            st.metric("거래수",   f"{out_result['count']}회")
                            st.metric("승률",     f"{out_result['win_rate']:.1f}%")
                            st.metric("평균수익", f"{out_result['avg_ret']:+.2f}%")
                            st.metric("샤프",     f"{out_result['sharpe']:.2f}")
                            st.metric("MDD",      f"{out_result['mdd']:.2f}%")

                    # Interpretation
                    if in_result is not None and out_result is not None:
                        st.markdown("---")
                        wr_diff = abs(out_result["win_rate"] - in_result["win_rate"])
                        if wr_diff <= 10:
                            st.success(
                                f"✅ 과적합 없음 — In-Sample 승률 {in_result['win_rate']:.1f}%와 "
                                f"Out-of-Sample 승률 {out_result['win_rate']:.1f}%의 차이가 "
                                f"{wr_diff:.1f}%p로 10%p 이내입니다."
                            )
                        else:
                            st.warning(
                                f"⚠️ 과적합 의심 — In-Sample 승률 {in_result['win_rate']:.1f}%와 "
                                f"Out-of-Sample 승률 {out_result['win_rate']:.1f}%의 차이가 "
                                f"{wr_diff:.1f}%p로 10%p를 초과합니다."
                            )

                        # Bar chart comparison
                        metrics_labels = ["승률(%)", "평균수익(%)", "샤프"]
                        in_vals  = [
                            in_result["win_rate"],
                            in_result["avg_ret"],
                            in_result["sharpe"],
                        ]
                        out_vals = [
                            out_result["win_rate"],
                            out_result["avg_ret"],
                            out_result["sharpe"],
                        ]

                        fig_wf = go.Figure(data=[
                            go.Bar(
                                name="In-Sample",
                                x=metrics_labels,
                                y=in_vals,
                                marker_color="#3498DB",
                            ),
                            go.Bar(
                                name="Out-of-Sample",
                                x=metrics_labels,
                                y=out_vals,
                                marker_color="#E74C3C",
                            ),
                        ])
                        fig_wf.update_layout(
                            barmode="group",
                            title="In-Sample vs Out-of-Sample 성과 비교",
                            height=350,
                            plot_bgcolor="#FAFAFA",
                            paper_bgcolor="#FFFFFF",
                            font_color="#333333",
                            xaxis=dict(gridcolor="#E8E8E8"),
                            yaxis=dict(gridcolor="#E8E8E8"),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        )
                        st.plotly_chart(fig_wf, use_container_width=True)
