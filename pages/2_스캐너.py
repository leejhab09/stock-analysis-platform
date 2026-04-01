"""
pages/2_스캐너.py — Multi-Factor Signal Scanner
전체 유니버스 스캔: RSI 신호 / MFI 신호 / BB 신호 / 3중 합치
"""

import streamlit as st
import pandas as pd
import numpy as np
from utils.quant_engine import (
    UNIVERSE, STRATEGY_INFO, TICKER_NAMES,
    get_vix, fetch_batch, get_signals,
)

st.set_page_config(page_title="스캐너", page_icon="🔍", layout="wide")
st.title("🔍 멀티팩터 신호 스캐너")
st.markdown("---")

# ─── VIX Guard ───────────────────────────────
vix, regime, regime_color = get_vix()

vix_col, ctrl_col = st.columns([1, 3])
with vix_col:
    if vix:
        st.markdown(f"""
        <div style='background:{regime_color}22;border-left:5px solid {regime_color};
                    padding:12px;border-radius:6px;'>
        <b>VIX: {vix:.2f}</b><br/>
        <span style='color:{regime_color}'>{regime}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("VIX 조회 실패")

if vix and vix >= 30:
    st.error("🚨 VIX ≥ 30 · 고변동 레짐 — 스캔 비활성화 (현금 보유 권고)")
    st.stop()

# ─── Controls ────────────────────────────────
with ctrl_col:
    c1, c2, c3 = st.columns(3)
    with c1:
        period = st.selectbox("조회 기간", ["3mo", "6mo", "1y"], index=0)
    with c2:
        groups = st.multiselect(
            "스캔 그룹",
            options=list(UNIVERSE.keys()),
            default=list(UNIVERSE.keys()),
        )
    with c3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        run_scan = st.button("▶ 스캔 실행", type="primary", use_container_width=True)

# ─── Strategy Explainer ─────────────────────
with st.expander("📖 전략 설명 — Multi-Factor Mean Reversion (Freqtrade-inspired)", expanded=False):
    st.markdown(STRATEGY_INFO["description"])

st.markdown("---")

# ─── Scan Logic ──────────────────────────────
if not run_scan:
    st.info("그룹을 선택하고 **▶ 스캔 실행** 버튼을 누르세요.")
    st.stop()

# Collect tickers for selected groups
all_tickers = []
group_map = {}  # ticker → group
for g in groups:
    for t in UNIVERSE.get(g, []):
        all_tickers.append(t)
        group_map[t] = g

if not all_tickers:
    st.warning("스캔할 종목이 없습니다.")
    st.stop()

# ─── Progress & Batch Download ───────────────
progress = st.progress(0, text="데이터 다운로드 중...")

# Split into US and KR tickers (KR tickers end with .KS)
us_tickers = [t for t in all_tickers if not t.endswith('.KS')]
kr_tickers = [t for t in all_tickers if t.endswith('.KS')]

data_map = {}
if us_tickers:
    progress.progress(20, text=f"미국 종목 {len(us_tickers)}개 다운로드...")
    data_map.update(fetch_batch(us_tickers, period=period))

if kr_tickers:
    progress.progress(60, text=f"한국 종목 {len(kr_tickers)}개 다운로드...")
    data_map.update(fetch_batch(kr_tickers, period=period))

progress.progress(80, text="신호 계산 중...")

# ─── Signal Calculation ───────────────────────
rows = []
for tkr, df in data_map.items():
    if df is None or df.empty or len(df) < 25:
        continue
    try:
        df_sig = get_signals(df)
        if 'buy_sig' not in df_sig.columns:
            continue

        last = df_sig.iloc[-1]
        rows.append({
            "그룹":       group_map.get(tkr, "?"),
            "티커":       tkr,
            "종목명":     TICKER_NAMES.get(tkr, tkr),
            "현재가":     round(float(last['Close']), 2),
            "RSI(14)":    round(float(last['rsi']), 1) if 'rsi' in df_sig.columns and not pd.isna(last['rsi']) else None,
            "MFI(14)":    round(float(last['mfi']), 1) if 'mfi' in df_sig.columns and not pd.isna(last['mfi']) else None,
            "BB하단":     round(float(last['bb_l']), 2) if 'bb_l' in df_sig.columns and not pd.isna(last['bb_l']) else None,
            "RSI신호":    bool(last['rsi_sig']) if 'rsi_sig' in df_sig.columns else False,
            "MFI신호":    bool(last['mfi_sig']) if 'mfi_sig' in df_sig.columns else False,
            "BB신호":     bool(last['bb_sig'])  if 'bb_sig'  in df_sig.columns else False,
            "3중합치":    bool(last['buy_sig']),
        })
    except Exception:
        continue

progress.progress(100, text="완료!")
progress.empty()

if not rows:
    st.warning("데이터를 가져온 종목이 없습니다. 잠시 후 다시 시도하세요.")
    st.stop()

df_result = pd.DataFrame(rows)

# ─── Summary Metrics ─────────────────────────
total = len(df_result)
rsi_hits   = df_result['RSI신호'].sum()
mfi_hits   = df_result['MFI신호'].sum()
bb_hits    = df_result['BB신호'].sum()
conf_hits  = df_result['3중합치'].sum()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("전체 종목", total)
m2.metric("RSI 과매도", int(rsi_hits), f"{rsi_hits/total*100:.0f}%")
m3.metric("MFI 과매도", int(mfi_hits), f"{mfi_hits/total*100:.0f}%")
m4.metric("BB 하단 터치", int(bb_hits), f"{bb_hits/total*100:.0f}%")
m5.metric("🎯 3중 합치", int(conf_hits), f"{conf_hits/total*100:.0f}%",
          delta_color="off" if conf_hits == 0 else "normal")

st.markdown("---")

# ─── Per-Strategy Tabs ────────────────────────
tab_conf, tab_rsi, tab_mfi, tab_bb, tab_all = st.tabs([
    "🎯 3중합치 (최종 신호)",
    "① RSI 신호",
    "② MFI 신호",
    "③ BB 신호",
    "📋 전체 결과",
])

def style_signal(val):
    if val is True or val == True:
        return "background-color:#004400;color:#00FF88;font-weight:bold"
    elif val is False or val == False:
        return "color:#555"
    return ""

def render_signal_table(df_sub: pd.DataFrame, signal_col: str):
    """신호 히트 종목 테이블 렌더링"""
    hits = df_sub[df_sub[signal_col] == True].copy()
    if hits.empty:
        st.info("현재 신호 없음")
        return

    # Group by category
    for grp in hits['그룹'].unique():
        grp_df = hits[hits['그룹'] == grp].drop(columns=['그룹'])
        st.markdown(f"**{grp}** ({len(grp_df)}개)")
        display_cols = ['티커', '종목명', '현재가', 'RSI(14)', 'MFI(14)', 'BB하단',
                        'RSI신호', 'MFI신호', 'BB신호', '3중합치']
        display_cols = [c for c in display_cols if c in grp_df.columns]
        styled = grp_df[display_cols].style.applymap(
            style_signal, subset=['RSI신호', 'MFI신호', 'BB신호', '3중합치']
        ).format({
            '현재가': '{:.2f}',
            'RSI(14)': '{:.1f}',
            'MFI(14)': '{:.1f}',
            'BB하단': '{:.2f}',
        }, na_rep='-')
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Tab: 3중합치 ───────────────────────────
with tab_conf:
    st.markdown("### 🎯 3중 합치 신호 (RSI + MFI + BB 동시 충족)")
    if vix and 20 <= vix < 30:
        st.warning(f"⚠️ VIX {vix:.1f} — 중변동 레짐. 포지션 축소 권고.")
    conf_df = df_result[df_result['3중합치'] == True].copy()
    if conf_df.empty:
        st.success("현재 3중 합치 신호 없음 — 과매도 영역에 진입한 종목이 없습니다.")
    else:
        st.error(f"🚨 {len(conf_df)}개 종목에서 3중 합치 신호 감지!")
        for grp in conf_df['그룹'].unique():
            grp_data = conf_df[conf_df['그룹'] == grp]
            st.markdown(f"**{grp}** ({len(grp_data)}개)")
            display_cols = ['티커', '종목명', '현재가', 'RSI(14)', 'MFI(14)', 'BB하단']
            styled = grp_data[display_cols].style.format({
                '현재가': '{:.2f}', 'RSI(14)': '{:.1f}',
                'MFI(14)': '{:.1f}', 'BB하단': '{:.2f}',
            }, na_rep='-').background_gradient(
                subset=['RSI(14)', 'MFI(14)'], cmap='RdYlGn', low=0, high=1
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Tab: RSI ──────────────────────────────
with tab_rsi:
    st.markdown("### ① RSI(14) < 35 — 과매도 종목")
    st.caption("RSI가 35 미만인 종목. 단독 신호는 참고용이며, 3중 합치를 최종 진입 기준으로 사용하세요.")
    render_signal_table(df_result, 'RSI신호')

# ── Tab: MFI ──────────────────────────────
with tab_mfi:
    st.markdown("### ② MFI(14) < 35 — 자금 이탈 종목")
    st.caption("MFI가 35 미만인 종목. 거래량 가중 RSI로, 스마트머니 이탈을 포착합니다.")
    render_signal_table(df_result, 'MFI신호')

# ── Tab: BB ───────────────────────────────
with tab_bb:
    st.markdown("### ③ Close ≤ BB Lower(20, 2σ) — 통계 하단 터치")
    st.caption("현재가가 볼린저밴드 하단(2σ) 이하인 종목. 통계적 과매도 영역 진입.")
    render_signal_table(df_result, 'BB신호')

# ── Tab: 전체 ─────────────────────────────
with tab_all:
    st.markdown("### 📋 전체 스캔 결과")

    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        show_grp = st.multiselect("그룹 필터", options=df_result['그룹'].unique().tolist(),
                                   default=df_result['그룹'].unique().tolist())
    with filter_col2:
        only_hits = st.checkbox("신호 있는 종목만", value=False)

    filtered = df_result[df_result['그룹'].isin(show_grp)].copy()
    if only_hits:
        filtered = filtered[
            filtered['RSI신호'] | filtered['MFI신호'] | filtered['BB신호']
        ]

    display_cols = ['그룹', '티커', '종목명', '현재가', 'RSI(14)', 'MFI(14)', 'BB하단',
                    'RSI신호', 'MFI신호', 'BB신호', '3중합치']
    styled = filtered[display_cols].style.applymap(
        style_signal, subset=['RSI신호', 'MFI신호', 'BB신호', '3중합치']
    ).format({
        '현재가': '{:.2f}',
        'RSI(14)': '{:.1f}',
        'MFI(14)': '{:.1f}',
        'BB하단': '{:.2f}',
    }, na_rep='-')
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(f"총 {len(filtered)}개 종목")

st.markdown("---")
st.caption("데이터: Yahoo Finance · 5분 캐시 · 신호 기준: 최근 확정봉")
