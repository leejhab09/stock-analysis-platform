"""
pages/3_전략시각화.py — Strategy Visualization
캔들차트 + BB + RSI + MFI + 매수/매도 신호 마커 (밝은 테마)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.quant_engine import (
    UNIVERSE, TICKER_NAMES, CHART_THEME,
    fetch_ohlcv, get_signals,
)

st.set_page_config(page_title="전략시각화", page_icon="📊", layout="wide")
st.title("📊 전략 시각화")
st.markdown("개별 종목의 기술 지표와 **매수·매도 신호**를 시각적으로 분석합니다.")
st.markdown("---")

# ─── Helper ──────────────────────────────────
def ax_style():
    return dict(gridcolor=CHART_THEME["gridcolor"],
                zerolinecolor=CHART_THEME["zerolinecolor"])

def light_layout(**kwargs):
    base = dict(
        plot_bgcolor=CHART_THEME["plot_bgcolor"],
        paper_bgcolor=CHART_THEME["paper_bgcolor"],
        font=dict(color=CHART_THEME["font_color"]),
    )
    base.update(kwargs)
    return base

# ─── Ticker Selection ────────────────────────
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

col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
with col1:
    _g_idx = _groups.index(st.session_state["shared_group"]) if st.session_state["shared_group"] in _groups else 0
    group_sel = st.selectbox("그룹 선택", _groups, index=_g_idx)
    st.session_state["shared_group"] = group_sel
with col2:
    tickers_in_group = UNIVERSE[group_sel]
    curr_ticker = st.session_state["shared_ticker"]
    if curr_ticker not in tickers_in_group:
        curr_ticker = tickers_in_group[0]
    curr_idx = tickers_in_group.index(curr_ticker)
    display_options = [f"{t} — {TICKER_NAMES.get(t, t)}" for t in tickers_in_group]
    sel_idx = st.selectbox("종목 선택", range(len(tickers_in_group)),
                           format_func=lambda i: display_options[i],
                           index=curr_idx)
    ticker_sel = tickers_in_group[sel_idx]
    st.session_state["shared_ticker"] = ticker_sel
with col3:
    _p_idx = _period_opts.index(st.session_state["shared_period"]) if st.session_state["shared_period"] in _period_opts else 2
    period = st.selectbox("기간", _period_opts, index=_p_idx)
    st.session_state["shared_period"] = period
with col4:
    hold_days = st.number_input("매도 보유일", min_value=1, max_value=60, value=st.session_state["shared_hold_days"])
    st.session_state["shared_hold_days"] = int(hold_days)

with st.expander("🔎 직접 티커 입력"):
    manual_ticker = st.text_input("티커 심볼 (예: AAPL, 005930.KS)", "").strip().upper()
    if manual_ticker:
        ticker_sel = manual_ticker

load_btn = st.button("📈 차트 로드", type="primary")

if not load_btn:
    st.info("종목을 선택하고 **📈 차트 로드** 버튼을 누르세요.")
    st.stop()

# ─── Data & Signals ──────────────────────────
with st.spinner(f"{ticker_sel} 데이터 로드 중..."):
    df = fetch_ohlcv(ticker_sel, period=period)

if df.empty:
    st.error(f"{ticker_sel} 데이터를 가져올 수 없습니다.")
    st.stop()

df = get_signals(df)
if 'buy_sig' not in df.columns:
    st.error("지표 계산 실패 — 데이터가 충분하지 않을 수 있습니다.")
    st.stop()

# Compute sell signals (hold_days after buy)
df['sell_sig'] = False
buy_indices = df.index[df['buy_sig'] == True].tolist()
sell_indices = []
for bi in buy_indices:
    pos = df.index.get_loc(bi)
    sell_pos = pos + hold_days
    if sell_pos < len(df):
        si = df.index[sell_pos]
        df.loc[si, 'sell_sig'] = True
        sell_indices.append(si)

# ─── Current Signal Status ───────────────────
last = df.iloc[-1]
ticker_name = TICKER_NAMES.get(ticker_sel, ticker_sel)
st.markdown(f"#### {ticker_sel} — {ticker_name}")

sig_cols = st.columns(6)
with sig_cols[0]:
    price = float(last['Close'])
    st.metric("현재가", f"{price:,.2f}")
with sig_cols[1]:
    if 'rsi' in df.columns and not pd.isna(last['rsi']):
        rsi_val = float(last['rsi'])
        rsi_lbl = "🔴 과매도" if rsi_val < 35 else ("🟡 중립" if rsi_val < 65 else "🟢 과매수")
        st.metric("RSI(14)", f"{rsi_val:.1f}", rsi_lbl, delta_color="off")
    else:
        st.metric("RSI(14)", "N/A")
with sig_cols[2]:
    if 'mfi' in df.columns and not pd.isna(last['mfi']):
        mfi_val = float(last['mfi'])
        mfi_lbl = "🔴 과매도" if mfi_val < 35 else ("🟡 중립" if mfi_val < 65 else "🟢 과매수")
        st.metric("MFI(14)", f"{mfi_val:.1f}", mfi_lbl, delta_color="off")
    else:
        st.metric("MFI(14)", "N/A")
with sig_cols[3]:
    if 'bb_l' in df.columns and not pd.isna(last['bb_l']):
        bb_l_val = float(last['bb_l'])
        bb_lbl = "🔴 하단 돌파" if price <= bb_l_val else "정상"
        st.metric("BB 하단", f"{bb_l_val:,.2f}", bb_lbl, delta_color="off")
    else:
        st.metric("BB 하단", "N/A")
with sig_cols[4]:
    buy_total = int(df['buy_sig'].sum())
    sell_total = len(sell_indices)
    st.metric("매수 신호", f"{buy_total}회")
with sig_cols[5]:
    if bool(last.get('buy_sig', False)):
        st.error("🚨 현재 매수 신호!")
    elif bool(last.get('sell_sig', False)):
        st.warning("📤 현재 매도 신호!")
    else:
        sig_count = sum([
            bool(last.get('rsi_sig', False)),
            bool(last.get('mfi_sig', False)),
            bool(last.get('bb_sig', False)),
        ])
        st.metric("신호 카운트", f"{sig_count}/3")

st.markdown("---")

# ─── Main Chart (4 rows) ─────────────────────
fig = make_subplots(
    rows=4, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.04,
    row_heights=[0.50, 0.18, 0.16, 0.16],
    subplot_titles=[
        f"{ticker_sel} 캔들 + 볼린저밴드  (▲매수  ▼매도 {hold_days}일 후)",
        "거래량 (Volume)",
        "RSI (14)  — 과매도 기준선 35",
        "MFI (14)  — 과매도 기준선 35",
    ],
)

# ── Row 1: Candlestick + BB ──────────────────
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['Open'], high=df['High'],
    low=df['Low'],   close=df['Close'],
    name="OHLC",
    increasing_line_color="#27AE60",
    decreasing_line_color="#E74C3C",
    increasing_fillcolor="#D5F5E3",
    decreasing_fillcolor="#FADBD8",
), row=1, col=1)

if 'bb_u' in df.columns:
    fig.add_trace(go.Scatter(
        x=df.index, y=df['bb_u'],
        mode='lines', name='BB Upper',
        line=dict(color='rgba(52,152,219,0.5)', width=1, dash='dot'),
        showlegend=True,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['bb_m'],
        mode='lines', name='BB Mid',
        line=dict(color='rgba(52,152,219,0.35)', width=1),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['bb_l'],
        mode='lines', name='BB Lower',
        line=dict(color='rgba(52,152,219,0.5)', width=1, dash='dot'),
        fill='tonexty', fillcolor='rgba(52,152,219,0.04)',
    ), row=1, col=1)

# Buy signal markers ▲
if buy_total > 0:
    sig_df = df[df['buy_sig'] == True]
    fig.add_trace(go.Scatter(
        x=sig_df.index,
        y=sig_df['Low'] * 0.985,
        mode='markers',
        name='▲ 매수',
        marker=dict(symbol='triangle-up', color='#27AE60', size=12,
                    line=dict(color='#1A6B34', width=1)),
    ), row=1, col=1)

# Sell signal markers ▼
if sell_indices:
    sell_df = df.loc[[i for i in sell_indices if i in df.index]]
    fig.add_trace(go.Scatter(
        x=sell_df.index,
        y=sell_df['High'] * 1.015,
        mode='markers',
        name='▼ 매도',
        marker=dict(symbol='triangle-down', color='#E74C3C', size=12,
                    line=dict(color='#8B0000', width=1)),
    ), row=1, col=1)

# Buy→Sell connector lines (show holding periods)
for bi, si in zip(buy_indices, sell_indices):
    if bi in df.index and si in df.index:
        buy_p  = float(df.loc[bi, 'Low']) * 0.985
        sell_p = float(df.loc[si, 'High']) * 1.015
        ret = (float(df.loc[si, 'Close']) / float(df.loc[bi, 'Close']) - 1) * 100
        line_color = "rgba(39,174,96,0.3)" if ret >= 0 else "rgba(231,76,60,0.3)"
        fig.add_shape(
            type="line",
            x0=bi, y0=buy_p, x1=si, y1=sell_p,
            line=dict(color=line_color, width=1, dash="dot"),
            row=1, col=1,
        )

# ── Row 2: Volume ────────────────────────────
vol_colors = [
    '#D5F5E3' if c >= o else '#FADBD8'
    for c, o in zip(df['Close'], df['Open'])
]
fig.add_trace(go.Bar(
    x=df.index, y=df['Volume'],
    name='Volume',
    marker_color=vol_colors,
    opacity=0.7,
    showlegend=False,
), row=2, col=1)

# ── Row 3: RSI ───────────────────────────────
if 'rsi' in df.columns:
    rsi_colors = ['#27AE60' if v >= 35 else '#E74C3C' for v in df['rsi'].fillna(50)]
    fig.add_trace(go.Scatter(
        x=df.index, y=df['rsi'],
        mode='lines', name='RSI',
        line=dict(color='#8E44AD', width=1.5),
    ), row=3, col=1)
    # Shade oversold region
    fig.add_hrect(y0=0, y1=35, fillcolor="rgba(231,76,60,0.07)",
                  line_width=0, row=3, col=1)
    fig.add_hline(y=35, line_dash="dash", line_color="#E74C3C", line_width=1,
                  annotation_text="35 과매도", annotation_position="right",
                  annotation_font_color="#E74C3C", row=3, col=1)
    fig.add_hline(y=65, line_dash="dash", line_color="#27AE60", line_width=1,
                  annotation_text="65 과매수", annotation_position="right",
                  annotation_font_color="#27AE60", row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#BBBBBB", line_width=1, row=3, col=1)

# ── Row 4: MFI ───────────────────────────────
if 'mfi' in df.columns:
    mfi_colors = ['#E74C3C' if v < 35 else ('#27AE60' if v > 65 else '#3498DB')
                  for v in df['mfi'].fillna(50)]
    fig.add_trace(go.Bar(
        x=df.index, y=df['mfi'],
        name='MFI', marker_color=mfi_colors, opacity=0.75,
    ), row=4, col=1)
    fig.add_hrect(y0=0, y1=35, fillcolor="rgba(231,76,60,0.07)",
                  line_width=0, row=4, col=1)
    fig.add_hline(y=35, line_dash="dash", line_color="#E74C3C", line_width=1,
                  annotation_text="35", annotation_position="right",
                  annotation_font_color="#E74C3C", row=4, col=1)
    fig.add_hline(y=65, line_dash="dash", line_color="#27AE60", line_width=1,
                  annotation_text="65", annotation_position="right",
                  annotation_font_color="#27AE60", row=4, col=1)

# ── Layout ───────────────────────────────────
fig.update_layout(
    height=820,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                bgcolor="rgba(255,255,255,0.8)", bordercolor="#DDD", borderwidth=1),
    margin=dict(t=60, b=20, l=60, r=20),
    xaxis_rangeslider_visible=False,
    **light_layout()
)
for i in range(1, 5):
    fig.update_xaxes(**ax_style(), row=i, col=1)
    fig.update_yaxes(**ax_style(), row=i, col=1)

st.plotly_chart(fig, use_container_width=True)

# ─── Buy/Sell Signal History Table ───────────
st.markdown("---")
st.subheader("📋 매수 / 매도 신호 이력")

if buy_total > 0:
    trade_rows = []
    sell_idx_set = {df.index.get_loc(si): si for si in sell_indices if si in df.index}

    for j, bi in enumerate(buy_indices):
        bi_pos = df.index.get_loc(bi)
        sell_pos = bi_pos + hold_days
        has_sell = sell_pos < len(df)
        sell_date = df.index[sell_pos] if has_sell else None
        buy_price  = float(df.loc[bi, 'Close'])
        sell_price = float(df.iloc[sell_pos]['Close']) if has_sell else None
        ret = (sell_price / buy_price - 1) * 100 if sell_price else None
        trade_rows.append({
            "매수일":     bi.date(),
            "매수가":     round(buy_price, 2),
            "매도일":     sell_date.date() if sell_date is not None else "보유중",
            "매도가":     round(sell_price, 2) if sell_price else "-",
            "수익률(%)":  f"{ret:+.2f}%" if ret is not None else "진행중",
            "결과":       ("✅ 수익" if ret and ret > 0 else ("❌ 손실" if ret and ret <= 0 else "⏳")),
            "RSI":        round(float(df.loc[bi, 'rsi']), 1) if 'rsi' in df.columns else "-",
            "MFI":        round(float(df.loc[bi, 'mfi']), 1) if 'mfi' in df.columns else "-",
        })

    trades_df = pd.DataFrame(trade_rows).sort_values("매수일", ascending=False)

    def color_result(val):
        if "✅" in str(val): return "color:#27AE60;font-weight:bold"
        if "❌" in str(val): return "color:#E74C3C;font-weight:bold"
        return "color:#888"

    st.dataframe(
        trades_df.style.applymap(color_result, subset=["결과"]),
        use_container_width=True, hide_index=True,
    )

    # Quick stats
    closed = [r for r in trade_rows if isinstance(r["매도가"], float)]
    if closed:
        rets = [float(r["수익률(%)"].replace('%','').replace('+','')) for r in closed]
        import numpy as np
        wc1, wc2, wc3, wc4 = st.columns(4)
        wc1.metric("총 거래", len(closed))
        wc2.metric("승률", f"{sum(1 for r in rets if r>0)/len(rets)*100:.0f}%")
        wc3.metric("평균 수익률", f"{np.mean(rets):+.2f}%")
        wc4.metric("누적 수익률", f"{sum(rets):+.2f}%")
else:
    st.info(f"선택 기간 내 매수 신호 없음")

st.markdown("---")
st.caption(f"▲ 매수: RSI<35 AND MFI<35 AND Close≤BB하단  |  ▼ 매도: 매수 후 {hold_days} 거래일 경과  |  데이터: Yahoo Finance")
