"""
국내 주식 페이퍼 매매 — 국내 시장 특화 다중 조건 전략
조건: 당일 낙폭 + RSI + 지수 대비 초과 낙폭 + 거래량 급등 + 볼린저 하단
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.notify import send_telegram
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh

from utils.kr_stock_data import (
    analyze_kr_ticker, get_kospi_change, get_kosdaq_change,
    KR_POPULAR, suffix
)

st.set_page_config(page_title="🇰🇷 국내 페이퍼매매", layout="wide")

DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "data")
KR_PORT_FILE  = os.path.join(DATA_DIR, "kr_portfolio.json")
KR_TRAD_FILE  = os.path.join(DATA_DIR, "kr_paper_trades.json")
KR_STRAT_FILE = os.path.join(DATA_DIR, "kr_strategy_config.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

portfolio = load_json(KR_PORT_FILE, [])
trades    = load_json(KR_TRAD_FILE, [])
strategy  = load_json(KR_STRAT_FILE, {
    "drop_threshold": -3.0, "rsi_threshold": 35,
    "relative_drop":  -2.0, "vol_ratio_min": 1.5,
    "bb_threshold":   0.2,  "budget_krw":    500000,
    "use_rsi": True, "use_relative": True,
    "use_volume": True, "use_bb": True,
    "watch_tickers": [],
})

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("<h2 style='color:#c0392b; background:#FFF0F0; padding:12px 20px; border-radius:10px; border-left:6px solid #c0392b;'>🇰🇷 국내 주식 페이퍼 매매</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#666;font-size:.85rem;'>"
    "국내 시장 특화 전략 · 낙폭 + RSI + 지수대비 + 거래량 + 볼린저 하단 · 자동 기록"
    "</p>", unsafe_allow_html=True,
)

st.markdown("""
<div style='display:flex; gap:12px; margin-bottom:8px;'>
  <div style='flex:1; background:#f8f8f8; border:2px solid #ccc; border-radius:10px;
              padding:14px; text-align:center;'>
    <div style='font-size:1.5rem;'>🇺🇸</div>
    <div style='font-weight:800; color:#888; font-size:1rem;'>미국 주식 → 5_미국_페이퍼매매</div>
    <div style='font-size:0.78rem; color:#888; margin-top:4px;'>
      통화: USD · 시장: NYSE/NASDAQ<br>
      장시간: ET 09:30~16:00 (KST 22:30~05:00)<br>
      조건: 낙폭 + RSI + 52주고점 + <b>VIX</b>
    </div>
  </div>
  <div style='flex:1; background:#FFF0F0; border:2px solid #c0392b; border-radius:10px;
              padding:14px; text-align:center;'>
    <div style='font-size:1.5rem;'>🇰🇷</div>
    <div style='font-weight:800; color:#c0392b; font-size:1rem;'>국내 주식 (현재 페이지)</div>
    <div style='font-size:0.78rem; color:#555; margin-top:4px;'>
      통화: KRW · 시장: KOSPI/KOSDAQ<br>
      장시간: KST 09:00~15:30<br>
      조건: 낙폭 + RSI + 지수대비 + <b>거래량 + %B</b>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 전략 설정")

    st.markdown("**① 당일 낙폭 (필수)**")
    drop_threshold = st.slider("낙폭 기준 (%)", -20.0, -0.5,
                                float(strategy["drop_threshold"]), 0.5)

    st.markdown("**② RSI 과매도**")
    use_rsi = st.checkbox("RSI 사용", value=strategy["use_rsi"])
    rsi_threshold = st.slider("RSI 상한 (이하 매수)", 15, 50,
                               int(strategy["rsi_threshold"]), 1, disabled=not use_rsi)

    st.markdown("**③ 지수 대비 초과 낙폭**")
    use_relative = st.checkbox("지수 대비 사용", value=strategy["use_relative"])
    relative_drop = st.slider("초과 낙폭 기준 (%)", -15.0, -0.5,
                               float(strategy["relative_drop"]), 0.5,
                               disabled=not use_relative,
                               help="종목 낙폭 - KOSPI 낙폭 ≤ 이 값")

    st.markdown("**④ 거래량 급등**")
    use_volume = st.checkbox("거래량 사용", value=strategy["use_volume"])
    vol_ratio_min = st.slider("20일 평균 대비 배수", 1.0, 5.0,
                               float(strategy["vol_ratio_min"]), 0.1,
                               disabled=not use_volume)

    st.markdown("**⑤ 볼린저 하단 (%B)**")
    use_bb = st.checkbox("볼린저 사용", value=strategy["use_bb"])
    bb_threshold = st.slider("%B 상한 (이하 매수)", 0.0, 0.5,
                              float(strategy["bb_threshold"]), 0.05,
                              disabled=not use_bb)

    st.markdown("---")
    budget_krw = st.number_input("1회 매수 예산 (원)", 100000, 10000000,
                                  int(strategy["budget_krw"]), 100000,
                                  format="%d")

    if st.button("💾 전략 저장", type="primary", use_container_width=True):
        strategy.update({
            "drop_threshold": drop_threshold, "rsi_threshold": rsi_threshold,
            "relative_drop": relative_drop,  "vol_ratio_min": vol_ratio_min,
            "bb_threshold": bb_threshold,    "budget_krw": budget_krw,
            "use_rsi": use_rsi, "use_relative": use_relative,
            "use_volume": use_volume, "use_bb": use_bb,
        })
        save_json(KR_STRAT_FILE, strategy)
        st.success("저장 완료")

    st.markdown("---")
    st.markdown("### ➕ 포트폴리오 추가")
    with st.form("kr_add"):
        tk   = st.text_input("티커", placeholder="005930 또는 005930.KS").strip()
        qty  = st.number_input("수량(주)", min_value=1, value=10, step=1)
        avg  = st.number_input("평균단가(원)", min_value=1, value=70000, step=100)
        memo = st.text_input("메모")
        if st.form_submit_button("추가", type="primary"):
            portfolio.append({"ticker": suffix(tk), "qty": qty,
                              "avg_price": avg, "memo": memo})
            save_json(KR_PORT_FILE, portfolio)
            st.success(f"{suffix(tk)} 추가")
            st.rerun()

# ── 전략 조건 요약 ────────────────────────────────────────────
st.markdown("### 🎯 매수 조건")
cc = st.columns(5)
cc[0].info(f"**① 낙폭**\n{drop_threshold:.1f}%↓")
cc[1].info(f"**② RSI**\n{'<'+str(rsi_threshold) if use_rsi else '미사용'}")
cc[2].info(f"**③ 지수대비**\n{relative_drop:.1f}% {'(사용)' if use_relative else '(미사용)'}")
cc[3].info(f"**④ 거래량**\n{vol_ratio_min:.1f}x↑ {'(사용)' if use_volume else '(미사용)'}")
cc[4].info(f"**⑤ %B**\n≤{bb_threshold:.2f} {'(사용)' if use_bb else '(미사용)'}")

st.divider()

# ── 인기 종목 목록 ────────────────────────────────────────────
with st.expander("📌 인기 종목 목록 (클릭해서 감시 추가)"):
    cols = st.columns(5)
    for i, (tk, name, sector) in enumerate(KR_POPULAR):
        with cols[i % 5]:
            st.markdown(f"""
            <div style='border:1px solid #CBD5E1;border-radius:6px;padding:8px;
                        text-align:center;background:#FFF5F5;'>
                <b style='color:#c0392b;'>{tk.replace('.KS','')}</b><br>
                <small>{name}</small><br>
                <small style='color:#888;'>{sector}</small>
            </div>""", unsafe_allow_html=True)

# ── 시세 조회 ─────────────────────────────────────────────────
port_tickers  = [h["ticker"] for h in portfolio]
watch_tickers = list(set(port_tickers + strategy.get("watch_tickers", [])))

if not watch_tickers:
    st.warning("포트폴리오에 종목을 추가하세요 (사이드바)")
    st.stop()

st.subheader("📡 시세 & 기술 지표")

@st.cache_data(ttl=300)
def fetch_all(tickers, kospi, kosdaq):
    return [r for r in (analyze_kr_ticker(t) for t in tickers) if r]

with st.spinner("국내 시세 분석 중..."):
    kospi_chg  = get_kospi_change()
    kosdaq_chg = get_kosdaq_change()
    analyses   = fetch_all(watch_tickers, kospi_chg, kosdaq_chg)

if not analyses:
    st.error("데이터 조회 실패")
    st.stop()

df = pd.DataFrame(analyses)

# 비중 계산
price_map = {r["ticker"]: r["curr_price"] for r in analyses}
total_val = sum(h["qty"] * price_map.get(suffix(h["ticker"]), h["avg_price"]) for h in portfolio)
weights   = {
    suffix(h["ticker"]): round(h["qty"] * price_map.get(suffix(h["ticker"]), h["avg_price"]) / total_val * 100, 2)
    for h in portfolio
} if total_val > 0 else {}
df["weight_%"]     = df["ticker"].map(weights).fillna(0)
df["in_portfolio"] = df["ticker"].isin(port_tickers)

# ── 지수 현황 ─────────────────────────────────────────────────
ic1, ic2, ic3 = st.columns(3)
ic1.metric("KOSPI 등락", f"{kospi_chg:+.2f}%" if kospi_chg else "N/A",
           delta_color="normal" if kospi_chg and kospi_chg >= 0 else "inverse")
ic2.metric("KOSDAQ 등락", f"{kosdaq_chg:+.2f}%" if kosdaq_chg else "N/A",
           delta_color="normal" if kosdaq_chg and kosdaq_chg >= 0 else "inverse")
ic3.metric("감시 종목", f"{len(watch_tickers)}개")

st.divider()

# ── 조건 체크 ─────────────────────────────────────────────────
def check_conditions(row):
    conds = {}
    conds["당일 낙폭"] = (row["change_pct"] <= drop_threshold,
                          f"{row['change_pct']:+.2f}%")
    if use_rsi:
        conds["RSI"] = (row["rsi"] <= rsi_threshold,
                        f"RSI={row['rsi']:.1f}")
    if use_relative and kospi_chg is not None:
        idx_chg = kosdaq_chg if row["market"] == "KOSDAQ" else kospi_chg
        excess  = row["change_pct"] - idx_chg
        conds["지수대비"] = (excess <= relative_drop,
                             f"초과낙폭={excess:+.2f}%")
    if use_volume:
        conds["거래량"] = (row["vol_ratio"] >= vol_ratio_min,
                           f"{row['vol_ratio']:.1f}x")
    if use_bb:
        conds["%B"] = (row["bb_pct"] <= bb_threshold,
                       f"%B={row['bb_pct']:.2f}")
    return all(v[0] for v in conds.values()), conds

df["passed"], df["_conds"] = zip(*df.apply(check_conditions, axis=1))

# ── 지표 테이블 ───────────────────────────────────────────────
disp = df[["ticker","name","market","curr_price","change_pct",
           "rsi","vol_ratio","bb_pct","drop_52w","weight_%","passed"]].copy()
disp.columns = ["티커","종목명","시장","현재가(원)","낙폭(%)","RSI","거래량배율","%B","52주낙폭(%)","비중(%)","조건통과"]
disp["조건통과"] = disp["조건통과"].map({True:"✅ 통과", False:"❌"})
disp["현재가(원)"] = disp["현재가(원)"].apply(lambda x: f"₩{x:,}")
st.dataframe(disp, use_container_width=True, height=280, hide_index=True)

# ── 차트 ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    colors = ["#16a34a" if p else ("#ef4444" if v >= 0 else "#3b82f6")
              for p, v in zip(df["passed"], df["change_pct"])]
    fig = go.Figure(go.Bar(
        x=df["ticker"].str.replace(".KS","").str.replace(".KQ",""),
        y=df["change_pct"],
        marker_color=colors,
        text=df["change_pct"].apply(lambda x: f"{x:+.1f}%"),
        textposition="outside",
        customdata=df["name"].values,
        hovertemplate="<b>%{customdata}</b><br>%{y:+.2f}%<extra></extra>",
    ))
    if kospi_chg:
        fig.add_hline(y=kospi_chg, line_dash="dot", line_color="gray",
                      annotation_text=f"KOSPI {kospi_chg:+.2f}%")
    fig.add_hline(y=drop_threshold, line_dash="dash", line_color="red",
                  annotation_text=f"트리거 {drop_threshold:.1f}%")
    fig.update_layout(title="당일 등락률", height=320,
                      plot_bgcolor="white", yaxis=dict(gridcolor="#f0f0f0"))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig2 = go.Figure()
    for _, row in df.iterrows():
        color = "#16a34a" if row["passed"] else "#94a3b8"
        size  = max(8, row["weight_%"] * 2 + 8)
        name  = row["ticker"].replace(".KS","").replace(".KQ","")
        fig2.add_trace(go.Scatter(
            x=[row["change_pct"]], y=[row["rsi"]],
            mode="markers+text",
            marker=dict(size=size, color=color, opacity=0.8),
            text=[name], textposition="top center",
            showlegend=False,
            hovertemplate=f"<b>{row['name']}</b><br>낙폭: {row['change_pct']:+.2f}%<br>RSI: {row['rsi']}<br>거래량: {row['vol_ratio']:.1f}x<br>%B: {row['bb_pct']:.2f}<extra></extra>",
        ))
    fig2.add_vline(x=drop_threshold, line_dash="dash", line_color="red")
    if use_rsi:
        fig2.add_hline(y=rsi_threshold, line_dash="dash", line_color="orange",
                       annotation_text=f"RSI {rsi_threshold}")
    fig2.update_layout(title="낙폭 vs RSI (크기=포트비중, 초록=통과)",
                       xaxis_title="낙폭(%)", yaxis_title="RSI",
                       height=320, plot_bgcolor="white",
                       xaxis=dict(gridcolor="#f0f0f0"),
                       yaxis=dict(gridcolor="#f0f0f0", range=[0,100]))
    st.plotly_chart(fig2, use_container_width=True)

# 거래량 & %B 차트
col3, col4 = st.columns(2)
with col3:
    fig3 = go.Figure(go.Bar(
        x=df["ticker"].str.replace(".KS","").str.replace(".KQ",""),
        y=df["vol_ratio"],
        marker_color=["#16a34a" if v >= vol_ratio_min else "#cbd5e1" for v in df["vol_ratio"]],
        text=df["vol_ratio"].apply(lambda x: f"{x:.1f}x"),
        textposition="outside",
    ))
    fig3.add_hline(y=vol_ratio_min, line_dash="dash", line_color="orange",
                   annotation_text=f"기준 {vol_ratio_min:.1f}x")
    fig3.update_layout(title="거래량 배율 (20일 평균 대비)", height=280,
                       plot_bgcolor="white", yaxis=dict(gridcolor="#f0f0f0"))
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    fig4 = go.Figure(go.Bar(
        x=df["ticker"].str.replace(".KS","").str.replace(".KQ",""),
        y=df["bb_pct"],
        marker_color=["#16a34a" if v <= bb_threshold else "#cbd5e1" for v in df["bb_pct"]],
        text=df["bb_pct"].apply(lambda x: f"{x:.2f}"),
        textposition="outside",
    ))
    fig4.add_hline(y=bb_threshold, line_dash="dash", line_color="orange",
                   annotation_text=f"기준 %B≤{bb_threshold:.2f}")
    fig4.add_hline(y=0.5, line_dash="dot", line_color="gray", annotation_text="중간")
    fig4.update_layout(title="볼린저 밴드 %B (낮을수록 하단 근접)", height=280,
                       plot_bgcolor="white", yaxis=dict(gridcolor="#f0f0f0", range=[-0.2,1.2]))
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── 매수 신호 ─────────────────────────────────────────────────
st.subheader("🚨 매수 신호")
passed_df = df[df["passed"]].copy()

if passed_df.empty:
    st.success("현재 조건 미충족 — 신호 없음")
else:
    st.warning(f"**{len(passed_df)}개 종목** 조건 통과!")
    send_telegram(f"[국내 매수신호] {len(passed_df)}개 종목 조건 통과\n" + "\n".join(passed_df["name"].tolist()))

    # 매수 대상 선정 (리밸런싱 스코어)
    port_passed = passed_df[passed_df["in_portfolio"]]
    if not port_passed.empty:
        port_passed = port_passed.copy()
        port_passed["score"] = (
            (1 - port_passed["weight_%"] / 100) * 0.5 +
            (-port_passed["change_pct"] / 30)   * 0.3 +
            (1 - port_passed["bb_pct"])          * 0.2
        )
        target = port_passed.sort_values("score", ascending=False).iloc[0]
        reason = f"리밸런싱 (비중{target['weight_%']:.1f}% 낙폭{target['change_pct']:+.2f}%)"
    else:
        target = passed_df.sort_values("change_pct").iloc[0]
        reason = f"감시종목 최대낙폭"

    exec_price = target["curr_price"]
    exec_qty   = max(1, int(budget_krw / exec_price))

    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        st.markdown(f"""
        <div style='background:#FFF0F0;border:2px solid #c0392b;border-radius:10px;
                    padding:20px;text-align:center;'>
            <div style='font-size:1.6rem;font-weight:900;color:#c0392b;'>
                {target['ticker'].replace('.KS','').replace('.KQ','')}
            </div>
            <div style='font-size:0.85rem;'>{target['name']} ({target['market']})</div>
            <div style='font-size:1.2rem;font-weight:700;margin-top:8px;'>
                ₩{exec_price:,}
            </div>
            <div style='font-size:0.8rem;color:#666;'>{reason}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown("**조건 점검**")
        _, conds = check_conditions(target)
        for cname, (ok, desc) in conds.items():
            st.markdown(f"{'✅' if ok else '❌'} **{cname}**: {desc}")

    with c3:
        st.markdown("**매수 실행**")
        e_qty   = st.number_input("수량 (주)", min_value=1, value=exec_qty, step=1)
        e_price = st.number_input("체결가 (원)", min_value=1, value=exec_price, step=100)
        e_memo  = st.text_input("메모",
                    value=f"낙폭{target['change_pct']:+.2f}% RSI{target['rsi']} 거래량{target['vol_ratio']:.1f}x")

        if st.button(f"✅ {target['ticker'].replace('.KS','').replace('.KQ','')} 매수 기록",
                     type="primary"):
            new_trade = {
                "id":          len(trades) + 1,
                "date":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action":      "BUY",
                "ticker":      target["ticker"],
                "name":        target["name"],
                "market":      target["market"],
                "price":       e_price,
                "qty":         e_qty,
                "amount_krw":  e_price * e_qty,
                "rsi_at_buy":  target["rsi"],
                "drop_pct":    target["change_pct"],
                "vol_ratio":   target["vol_ratio"],
                "bb_pct":      target["bb_pct"],
                "drop_52w":    target["drop_52w"],
                "kospi_at_buy":kospi_chg,
                "reason":      reason,
                "memo":        e_memo,
                "status":      "open",
                "sell_price":  None,
                "pnl_krw":     None,
            }
            trades.append(new_trade)
            save_json(KR_TRAD_FILE, trades)
            st.success(f"✅ {target['name']} {e_qty}주 @ ₩{e_price:,} 기록!")
            st.balloons()

st.divider()

# ── 거래 기록 ─────────────────────────────────────────────────
st.subheader("📒 국내 거래 기록")

if not trades:
    st.info("아직 거래 기록이 없습니다.")
else:
    df_t = pd.DataFrame(trades)

    # 미실현 손익
    def calc_pnl(row):
        if row["status"] == "closed":
            return row.get("pnl_krw")
        curr = price_map.get(row["ticker"])
        return round((curr - row["price"]) * row["qty"]) if curr else None

    df_t["미실현손익"] = df_t.apply(calc_pnl, axis=1)
    df_t["수익률%"]   = df_t.apply(
        lambda r: round(r["미실현손익"] / (r["price"] * r["qty"]) * 100, 2)
        if r["미실현손익"] is not None else None, axis=1
    )

    open_t   = df_t[df_t["status"] == "open"]
    closed_t = df_t[df_t["status"] == "closed"]
    invested = (open_t["price"] * open_t["qty"]).sum()
    unreal   = open_t["미실현손익"].dropna().sum()
    realized = closed_t["pnl_krw"].dropna().sum() if "pnl_krw" in closed_t.columns else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("총 거래",     f"{len(df_t)}건")
    k2.metric("오픈",        f"{len(open_t)}건")
    k3.metric("투자금",      f"₩{invested:,.0f}")
    k4.metric("미실현 손익", f"₩{unreal:+,.0f}",
              delta=f"{unreal/invested*100:+.2f}%" if invested > 0 else None)
    k5.metric("실현 손익",   f"₩{realized:+,.0f}")

    # 테이블
    show = ["id","date","ticker","name","market","price","qty","amount_krw",
            "rsi_at_buy","drop_pct","vol_ratio","미실현손익","수익률%","status"]
    show = [c for c in show if c in df_t.columns]
    disp_t = df_t[show].rename(columns={
        "id":"#","date":"날짜","ticker":"티커","name":"종목명","market":"시장",
        "price":"매수가","qty":"수량","amount_krw":"금액(₩)",
        "rsi_at_buy":"RSI","drop_pct":"낙폭%","vol_ratio":"거래량배율",
        "미실현손익":"손익(₩)","수익률%":"수익률%","status":"상태"
    })

    def color_pnl(val):
        try:
            v = float(val)
            if v > 0: return "color:#ef4444;font-weight:700"
            if v < 0: return "color:#3b82f6;font-weight:700"
        except: pass
        return ""

    try:    styled = disp_t.style.map(color_pnl, subset=["손익(₩)","수익률%"])
    except: styled = disp_t.style.applymap(color_pnl, subset=["손익(₩)","수익률%"])
    st.dataframe(styled, use_container_width=True, height=280, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        if len(open_t) > 0:
            pnl_g = open_t.groupby("ticker")["미실현손익"].sum().reset_index()
            pnl_g["ticker"] = pnl_g["ticker"].str.replace(".KS","").str.replace(".KQ","")
            fig_p = go.Figure(go.Bar(
                x=pnl_g["ticker"], y=pnl_g["미실현손익"],
                marker_color=["#ef4444" if v>=0 else "#3b82f6" for v in pnl_g["미실현손익"]],
                text=pnl_g["미실현손익"].apply(lambda x: f"₩{x:+,.0f}"),
                textposition="outside",
            ))
            fig_p.add_hline(y=0, line_color="gray")
            fig_p.update_layout(title="종목별 미실현 손익",
                                height=280, plot_bgcolor="white")
            st.plotly_chart(fig_p, use_container_width=True)

    with col2:
        if len(df_t) > 1:
            ds = df_t.sort_values("date").copy()
            ds["누적"] = (ds["price"] * ds["qty"]).cumsum()
            fig_c = px.area(ds, x="date", y="누적",
                            title="누적 투자금 추이",
                            labels={"date":"날짜","누적":"누적투자(₩)"})
            fig_c.update_layout(height=280)
            st.plotly_chart(fig_c, use_container_width=True)

    st.divider()
    st.markdown("### 💰 포지션 청산")
    open_ids = open_t["id"].tolist() if len(open_t) > 0 else []
    if open_ids:
        sel = st.selectbox("청산 거래 #", open_ids,
                           format_func=lambda i: f"#{i} {df_t[df_t['id']==i]['ticker'].values[0]}")
        orig = df_t[df_t["id"]==sel].iloc[0]
        curr_p = price_map.get(orig["ticker"], orig["price"])
        sell_p = st.number_input("매도가 (원)", min_value=1, value=int(curr_p), step=100)
        if st.button("✅ 매도 기록", type="secondary"):
            for t in trades:
                if t["id"] == sel:
                    pnl = (sell_p - t["price"]) * t["qty"]
                    t.update({"status":"closed","sell_price":sell_p,"pnl_krw":pnl})
            save_json(KR_TRAD_FILE, trades)
            st.success(f"청산 완료! 손익: ₩{pnl:+,.0f}")
            st.rerun()

    csv = df_t.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇ 거래 기록 CSV", csv, "kr_paper_trades.csv", "text/csv")
