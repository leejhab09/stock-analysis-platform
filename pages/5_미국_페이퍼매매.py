"""
페이퍼 매매 전략 v2 — 다중 조건 기반 스마트 매수
조건: 당일 낙폭 + RSI 과매도 + 52주 고점 대비 낙폭 + VIX 공황 감지
매수 대상: 포트폴리오 내 비중 낮고 낙폭 큰 종목 (리밸런싱 관점)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import datetime
import yfinance as yf

from utils.stock_data import get_usd_krw

st.set_page_config(page_title="🇺🇸 미국 페이퍼매매", layout="wide")

# ── 파일 경로 ─────────────────────────────────────────────────
DATA_DIR       = os.path.join(os.path.dirname(__file__), "..", "data")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
TRADES_FILE    = os.path.join(DATA_DIR, "paper_trades.json")
STRATEGY_FILE  = os.path.join(DATA_DIR, "strategy_config.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

portfolio = load_json(PORTFOLIO_FILE, [])
trades    = load_json(TRADES_FILE, [])
strategy  = load_json(STRATEGY_FILE, {
    "drop_threshold": -3.0,
    "rsi_threshold": 40,
    "high52w_drop": -20.0,
    "vix_caution": 25,
    "vix_half": 30,
    "budget_usd": 1000,
    "watch_tickers": [],
    "use_rsi": True,
    "use_52w": True,
    "use_vix": True,
})

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("<h2 style='color:#1a56db; background:#EBF5FF; padding:12px 20px; border-radius:10px; border-left:6px solid #1a56db;'>🇺🇸 미국 주식 페이퍼 매매</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#666;font-size:.85rem;'>"
    "다중 조건 필터 (낙폭 + RSI + 52주 고점 + VIX) · 리밸런싱 기반 매수 · 자동 기록"
    "</p>",
    unsafe_allow_html=True,
)

st.markdown("""
<div style='display:flex; gap:12px; margin-bottom:8px;'>
  <div style='flex:1; background:#EBF5FF; border:2px solid #1a56db; border-radius:10px;
              padding:14px; text-align:center;'>
    <div style='font-size:1.5rem;'>🇺🇸</div>
    <div style='font-weight:800; color:#1a56db; font-size:1rem;'>미국 주식 (현재 페이지)</div>
    <div style='font-size:0.78rem; color:#555; margin-top:4px;'>
      통화: USD · 시장: NYSE/NASDAQ<br>
      장시간: ET 09:30~16:00 (KST 22:30~05:00)<br>
      조건: 낙폭 + RSI + 52주고점 + <b>VIX</b>
    </div>
  </div>
  <div style='flex:1; background:#f8f8f8; border:2px solid #ccc; border-radius:10px;
              padding:14px; text-align:center;'>
    <div style='font-size:1.5rem;'>🇰🇷</div>
    <div style='font-weight:800; color:#888; font-size:1rem;'>국내 주식 → 6_국내_페이퍼매매</div>
    <div style='font-size:0.78rem; color:#888; margin-top:4px;'>
      통화: KRW · 시장: KOSPI/KOSDAQ<br>
      장시간: KST 09:00~15:30<br>
      조건: 낙폭 + RSI + 지수대비 + <b>거래량 + %B</b>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 사이드바: 전략 설정 ───────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 전략 설정")

    st.markdown("**① 낙폭 조건 (필수)**")
    drop_threshold = st.slider("당일 낙폭 기준 (%)", -15.0, -0.5,
                                float(strategy["drop_threshold"]), 0.5)

    st.markdown("**② RSI 조건**")
    use_rsi = st.checkbox("RSI 조건 사용", value=strategy["use_rsi"])
    rsi_threshold = st.slider("RSI 상한선 (이하일 때 매수)", 20, 60,
                               int(strategy["rsi_threshold"]), 1,
                               disabled=not use_rsi)

    st.markdown("**③ 52주 고점 대비 낙폭**")
    use_52w = st.checkbox("52주 낙폭 조건 사용", value=strategy["use_52w"])
    high52w_drop = st.slider("52주 고점 대비 낙폭 기준 (%)", -60.0, -5.0,
                              float(strategy["high52w_drop"]), 1.0,
                              disabled=not use_52w)

    st.markdown("**④ VIX 공황 감지**")
    use_vix = st.checkbox("VIX 조건 사용", value=strategy["use_vix"])
    vix_caution = st.slider("VIX 주의 기준 (경고)", 15, 40,
                             int(strategy["vix_caution"]), 1,
                             disabled=not use_vix)
    vix_half = st.slider("VIX 공황 기준 (예산 절반)", vix_caution, 50,
                          int(strategy["vix_half"]), 1,
                          disabled=not use_vix)

    st.markdown("**⑤ 매수 예산**")
    budget = st.number_input("1회 매수 예산 (USD)", 100, 100000,
                              int(strategy["budget_usd"]), 100)

    st.markdown("---")
    st.markdown("**감시 종목 추가**")
    extra = st.text_input("티커 (포트폴리오 외)", placeholder="SPY").upper().strip()
    if st.button("추가") and extra:
        wl = strategy.get("watch_tickers", [])
        if extra not in wl:
            wl.append(extra)
        strategy["watch_tickers"] = wl

    if st.button("💾 전략 저장", use_container_width=True, type="primary"):
        strategy.update({
            "drop_threshold": drop_threshold,
            "rsi_threshold": rsi_threshold,
            "high52w_drop": high52w_drop,
            "vix_caution": vix_caution,
            "vix_half": vix_half,
            "budget_usd": budget,
            "use_rsi": use_rsi,
            "use_52w": use_52w,
            "use_vix": use_vix,
        })
        save_json(STRATEGY_FILE, strategy)
        st.success("저장 완료")

# ── 전략 조건 요약 ────────────────────────────────────────────
st.markdown("### 🎯 현재 매수 조건")
cond_cols = st.columns(4)
cond_cols[0].info(f"**① 당일 낙폭**\n{drop_threshold:.1f}% 이하")
cond_cols[1].info(f"**② RSI**\n{'RSI < ' + str(rsi_threshold) if use_rsi else '조건 미사용'}")
cond_cols[2].info(f"**③ 52주 고점**\n{high52w_drop:.0f}% 이상 하락 {'(사용)' if use_52w else '(미사용)'}")
cond_cols[3].info(f"**④ VIX**\n{'>'+str(vix_half)+' → 예산 50%' if use_vix else '조건 미사용'}")
st.caption("매수 대상: 조건 통과 종목 중 **포트폴리오 비중 낮고 낙폭 큰 종목** (리밸런싱)")

st.divider()

# ── 시세 & 지표 조회 ─────────────────────────────────────────
portfolio_tickers = [h["ticker"] for h in portfolio]
watch_tickers     = list(set(portfolio_tickers + strategy.get("watch_tickers", [])))

if not watch_tickers:
    st.warning("포트폴리오에 종목이 없습니다. 💼 포트폴리오 페이지에서 종목을 추가하세요.")
    st.stop()

st.subheader("📡 시세 & 기술 지표 분석")

@st.cache_data(ttl=300)
def get_full_analysis(tickers):
    rows = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y", interval="1d")
            if hist.empty or len(hist) < 2:
                continue
            hist.index = hist.index.tz_localize(None)

            # 당일 등락
            prev_close  = hist["Close"].iloc[-2]
            curr_price  = hist["Close"].iloc[-1]
            change_pct  = (curr_price - prev_close) / prev_close * 100

            # 52주 고점 대비
            high_52w    = hist["Close"].max()
            drop_52w    = (curr_price - high_52w) / high_52w * 100

            # RSI (14일)
            delta = hist["Close"].diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / loss.replace(0, np.nan)
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

            # MA20 이격도
            ma20     = hist["Close"].rolling(20).mean().iloc[-1]
            ma_gap   = (curr_price - ma20) / ma20 * 100

            # 볼린저 밴드
            std20     = hist["Close"].rolling(20).std().iloc[-1]
            bb_lower  = ma20 - 2 * std20
            bb_pct    = (curr_price - bb_lower) / (2 * 2 * std20) * 100 if std20 > 0 else None

            info = t.info
            rows.append({
                "ticker":      ticker,
                "name":        info.get("shortName", ticker),
                "curr_price":  round(curr_price, 2),
                "change_pct":  round(change_pct, 2),
                "high_52w":    round(high_52w, 2),
                "drop_52w":    round(drop_52w, 2),
                "rsi":         round(rsi, 1) if rsi else None,
                "ma20_gap":    round(ma_gap, 2),
                "bb_lower":    round(bb_lower, 2),
            })
        except Exception as e:
            pass
    return rows

@st.cache_data(ttl=300)
def get_vix():
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="2d")
        return round(float(hist["Close"].iloc[-1]), 2)
    except:
        return None

with st.spinner("시세 및 기술 지표 분석 중... (약 10~20초)"):
    analysis = get_full_analysis(watch_tickers)
    vix_val  = get_vix()

if not analysis:
    st.error("데이터 조회 실패.")
    st.stop()

df = pd.DataFrame(analysis)
fx = get_usd_krw()

# ── 포트폴리오 비중 계산 ──────────────────────────────────────
price_map = {r["ticker"]: r["curr_price"] for r in analysis}
total_val = sum(h["qty"] * price_map.get(h["ticker"], h["avg_price"]) for h in portfolio)
weights   = {}
for h in portfolio:
    val = h["qty"] * price_map.get(h["ticker"], h["avg_price"])
    weights[h["ticker"]] = round(val / total_val * 100, 2) if total_val > 0 else 0

df["weight_%"]      = df["ticker"].map(weights).fillna(0)
df["in_portfolio"]  = df["ticker"].isin(portfolio_tickers)

# ── VIX 상태 표시 ─────────────────────────────────────────────
vix_col1, vix_col2 = st.columns([1, 3])
if vix_val:
    if vix_val >= vix_half and use_vix:
        vix_status = "🔴 공황 구간"
        vix_color  = "error"
        actual_budget = budget * 0.5
    elif vix_val >= vix_caution and use_vix:
        vix_status = "🟡 주의 구간"
        vix_color  = "warning"
        actual_budget = budget * 0.75
    else:
        vix_status = "🟢 정상 구간"
        vix_color  = "success"
        actual_budget = budget
    with vix_col1:
        getattr(st, vix_color)(f"**VIX: {vix_val:.1f}** — {vix_status}\n\n실제 매수 예산: **${actual_budget:,.0f}**")
else:
    actual_budget = budget
    with vix_col1:
        st.info("VIX 조회 실패 — 전체 예산 사용")

# ── 다중 조건 필터링 ──────────────────────────────────────────
def check_conditions(row):
    conds = {}
    conds["당일 낙폭"]   = (row["change_pct"] <= drop_threshold,
                            f"{row['change_pct']:+.2f}% (기준: {drop_threshold:.1f}%)")
    if use_rsi:
        rsi = row["rsi"]
        conds["RSI 과매도"] = (rsi is not None and rsi <= rsi_threshold,
                               f"RSI={rsi:.1f} (기준: ≤{rsi_threshold})" if rsi else "N/A")
    if use_52w:
        conds["52주 낙폭"] = (row["drop_52w"] <= high52w_drop,
                               f"{row['drop_52w']:+.2f}% (기준: ≤{high52w_drop:.0f}%)")
    passed = all(v[0] for v in conds.values())
    return passed, conds

df["passed"], df["conditions"] = zip(*df.apply(check_conditions, axis=1))

# ── 지표 현황 테이블 ──────────────────────────────────────────
st.markdown("#### 📊 종목별 기술 지표 현황")

def style_val(col, val):
    try:
        if col == "change_pct":
            return "color:#ef4444" if val >= 0 else ("color:#3b82f6;font-weight:700" if val <= drop_threshold else "color:#3b82f6")
        if col == "rsi" and use_rsi:
            return "color:#ef4444;font-weight:700" if val <= rsi_threshold else ""
        if col == "drop_52w" and use_52w:
            return "color:#f97316;font-weight:700" if val <= high52w_drop else ""
        if col == "passed":
            return "color:#16a34a;font-weight:800" if val else "color:#9ca3af"
    except:
        pass
    return ""

disp = df[["ticker","name","curr_price","change_pct","rsi","drop_52w","ma20_gap","weight_%","passed"]].copy()
disp.columns = ["티커","종목명","현재가($)","당일등락(%)","RSI","52주낙폭(%)","MA20이격(%)","비중(%)","조건통과"]
disp["조건통과"] = disp["조건통과"].map({True: "✅ 통과", False: "❌"})

st.dataframe(disp, use_container_width=True, height=280, hide_index=True)

# ── 낙폭 & RSI 산포도 ─────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    fig_bar = go.Figure(go.Bar(
        x=df["ticker"], y=df["change_pct"],
        marker_color=["#16a34a" if p else ("#ef4444" if v>=0 else "#3b82f6")
                      for p, v in zip(df["passed"], df["change_pct"])],
        text=df["change_pct"].apply(lambda x: f"{x:+.1f}%"),
        textposition="outside",
    ))
    fig_bar.add_hline(y=drop_threshold, line_dash="dash", line_color="red",
                      annotation_text=f"트리거 {drop_threshold:.1f}%")
    fig_bar.update_layout(title="당일 등락률 (초록=조건통과)", height=320,
                           plot_bgcolor="white", yaxis=dict(gridcolor="#f0f0f0"))
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    fig_scatter = go.Figure()
    for _, row in df.iterrows():
        color  = "#16a34a" if row["passed"] else "#94a3b8"
        size   = max(8, row["weight_%"] * 3 + 8)
        fig_scatter.add_trace(go.Scatter(
            x=[row["change_pct"]], y=[row["rsi"]],
            mode="markers+text",
            marker=dict(size=size, color=color, opacity=0.8),
            text=[row["ticker"]], textposition="top center",
            name=row["ticker"], showlegend=False,
            hovertemplate=f"<b>{row['ticker']}</b><br>낙폭: {row['change_pct']:+.2f}%<br>RSI: {row['rsi']}<br>비중: {row['weight_%']:.1f}%<extra></extra>",
        ))
    fig_scatter.add_vline(x=drop_threshold, line_dash="dash", line_color="red")
    if use_rsi:
        fig_scatter.add_hline(y=rsi_threshold, line_dash="dash", line_color="orange",
                               annotation_text=f"RSI {rsi_threshold}")
    fig_scatter.update_layout(
        title="낙폭 vs RSI (초록=조건통과, 크기=포트비중)",
        xaxis_title="당일 등락률 (%)", yaxis_title="RSI",
        height=320, plot_bgcolor="white",
        xaxis=dict(gridcolor="#f0f0f0"), yaxis=dict(gridcolor="#f0f0f0", range=[0,100]),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# ── 매수 신호 ─────────────────────────────────────────────────
st.subheader("🚨 매수 신호")
passed_df = df[df["passed"]].copy()

if passed_df.empty:
    active_conds = ["당일 낙폭"]
    if use_rsi:   active_conds.append(f"RSI≤{rsi_threshold}")
    if use_52w:   active_conds.append(f"52주 낙폭≤{high52w_drop:.0f}%")
    st.success(f"현재 조건 미충족 — 신호 없음 ({' + '.join(active_conds)})")
else:
    st.warning(f"**{len(passed_df)}개 종목**이 모든 조건 통과 → 매수 신호!")

    # 매수 대상 결정: 비중 낮고 낙폭 큰 종목 (리밸런싱)
    portfolio_passed = passed_df[passed_df["in_portfolio"]]
    if not portfolio_passed.empty:
        # 비중 낮을수록, 낙폭 클수록 점수 높음
        portfolio_passed = portfolio_passed.copy()
        portfolio_passed["score"] = (
            (1 - portfolio_passed["weight_%"] / 100) * 0.6 +
            (-portfolio_passed["change_pct"] / 100)  * 0.4
        )
        target = portfolio_passed.sort_values("score", ascending=False).iloc[0]
        select_reason = f"리밸런싱 (비중 {target['weight_%']:.1f}% + 낙폭 {target['change_pct']:+.2f}%)"
    else:
        # 포트폴리오 외 종목 중 낙폭 최대
        target = passed_df.sort_values("change_pct").iloc[0]
        select_reason = f"감시 종목 중 최대 낙폭 ({target['change_pct']:+.2f}%)"

    target_price = target["curr_price"]
    target_qty   = round(actual_budget / target_price, 4)

    # 신호 카드
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.markdown(f"""
        <div style='background:#F0FDF4;border:2px solid #16a34a;border-radius:10px;
                    padding:20px;text-align:center;'>
            <div style='font-size:1.8rem;font-weight:900;color:#1a56db;'>{target['ticker']}</div>
            <div style='font-size:0.85rem;color:#555;'>{target['name']}</div>
            <div style='font-size:1.3rem;font-weight:700;color:#dc2626;margin-top:8px;'>
                ${target_price:,.2f}
            </div>
            <div style='font-size:0.8rem;color:#666;margin-top:4px;'>{select_reason}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("**조건 점검**")
        for ticker_r in passed_df["ticker"].tolist():
            row = passed_df[passed_df["ticker"]==ticker_r].iloc[0]
            _, conds = check_conditions(row)
            for cname, (ok, desc) in conds.items():
                icon = "✅" if ok else "❌"
                st.markdown(f"{icon} **{cname}**: {desc}")
            st.markdown("---")
    with c3:
        st.markdown("**매수 실행**")
        exec_qty   = st.number_input("수량", min_value=0.001,
                                      value=float(target_qty), step=0.001, format="%.4f")
        exec_price = st.number_input("체결가 ($)", min_value=0.01,
                                      value=float(target_price), step=0.01)
        exec_memo  = st.text_input("메모",
            value=f"낙폭:{target['change_pct']:+.2f}% RSI:{target['rsi']} VIX:{vix_val}")

        if st.button(f"✅ {target['ticker']} 페이퍼 매수 기록", type="primary"):
            new_trade = {
                "id":            len(trades) + 1,
                "date":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action":        "BUY",
                "ticker":        target["ticker"],
                "name":          str(target["name"]),
                "price":         exec_price,
                "qty":           exec_qty,
                "amount_usd":    round(exec_price * exec_qty, 2),
                "rsi_at_buy":    target["rsi"],
                "drop_pct":      target["change_pct"],
                "drop_52w":      target["drop_52w"],
                "vix_at_buy":    vix_val,
                "select_reason": select_reason,
                "memo":          exec_memo,
                "status":        "open",
                "sell_price":    None,
                "pnl_usd":       None,
            }
            trades.append(new_trade)
            save_json(TRADES_FILE, trades)
            st.success(f"✅ {target['ticker']} {exec_qty}주 @ ${exec_price:.2f} 기록!")
            st.balloons()

st.divider()

# ── 거래 기록 ─────────────────────────────────────────────────
st.subheader("📒 거래 기록")

if not trades:
    st.info("아직 거래 기록이 없습니다.")
else:
    df_trades = pd.DataFrame(trades)

    # 미실현 손익 계산
    def calc_pnl(row):
        if row["status"] == "closed":
            return row.get("pnl_usd")
        curr = price_map.get(row["ticker"])
        if curr:
            return round((curr - row["price"]) * row["qty"], 2)
        return None

    df_trades["미실현손익"] = df_trades.apply(calc_pnl, axis=1)
    df_trades["수익률%"]    = df_trades.apply(
        lambda r: round(r["미실현손익"] / (r["price"] * r["qty"]) * 100, 2)
        if r["미실현손익"] is not None else None, axis=1
    )

    # KPI
    open_t   = df_trades[df_trades["status"] == "open"]
    closed_t = df_trades[df_trades["status"] == "closed"]
    invested = (open_t["price"] * open_t["qty"]).sum()
    unreal   = open_t["미실현손익"].dropna().sum()
    realized = closed_t["pnl_usd"].dropna().sum() if "pnl_usd" in closed_t else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("총 거래",     f"{len(df_trades)}건")
    k2.metric("오픈",        f"{len(open_t)}건")
    k3.metric("투자금",      f"${invested:,.0f}")
    k4.metric("미실현 손익", f"${unreal:+,.0f}",
              delta=f"{unreal/invested*100:+.2f}%" if invested > 0 else None)
    k5.metric("실현 손익",   f"${realized:+,.0f}")

    # 거래 테이블
    show_cols = ["id","date","ticker","price","qty","amount_usd",
                 "rsi_at_buy","drop_pct","vix_at_buy","미실현손익","수익률%","status"]
    show_cols = [c for c in show_cols if c in df_trades.columns]
    disp_t = df_trades[show_cols].copy()
    rename = {"id":"#","date":"날짜","ticker":"티커","price":"매수가",
              "qty":"수량","amount_usd":"금액($)","rsi_at_buy":"매수시RSI",
              "drop_pct":"낙폭(%)","vix_at_buy":"매수시VIX",
              "미실현손익":"손익($)","수익률%":"수익률(%)","status":"상태"}
    disp_t = disp_t.rename(columns=rename)

    def color_pnl(val):
        try:
            v = float(val)
            if v > 0: return "color:#ef4444;font-weight:700"
            if v < 0: return "color:#3b82f6;font-weight:700"
        except: pass
        return ""
    try:
        styled = disp_t.style.map(color_pnl, subset=["손익($)","수익률(%)"])
    except:
        styled = disp_t.style.applymap(color_pnl, subset=["손익($)","수익률(%)"])
    st.dataframe(styled, use_container_width=True, height=280, hide_index=True)

    # 차트
    col1, col2 = st.columns(2)
    with col1:
        if len(open_t) > 0:
            st.markdown("**오픈 포지션 손익**")
            tpnl = open_t.groupby("ticker")["미실현손익"].sum().reset_index()
            fig_pnl = go.Figure(go.Bar(
                x=tpnl["ticker"], y=tpnl["미실현손익"],
                marker_color=["#ef4444" if v >= 0 else "#3b82f6" for v in tpnl["미실현손익"]],
                text=tpnl["미실현손익"].apply(lambda x: f"${x:+,.0f}"),
                textposition="outside",
            ))
            fig_pnl.add_hline(y=0, line_color="gray")
            fig_pnl.update_layout(height=300, plot_bgcolor="white",
                                   yaxis_title="손익 (USD)")
            st.plotly_chart(fig_pnl, use_container_width=True)

    with col2:
        if len(df_trades) > 1:
            st.markdown("**누적 투자금 추이**")
            ds = df_trades.sort_values("date").copy()
            ds["누적"] = (ds["price"] * ds["qty"]).cumsum()
            fig_cum = px.area(ds, x="date", y="누적",
                              labels={"date":"날짜","누적":"누적투자(USD)"})
            fig_cum.update_layout(height=300)
            st.plotly_chart(fig_cum, use_container_width=True)

    # 매수 조건 분석 (RSI, VIX 분포)
    if len(df_trades) >= 3 and "rsi_at_buy" in df_trades.columns:
        st.markdown("**매수 시점 지표 분포**")
        c1, c2 = st.columns(2)
        with c1:
            rsi_vals = df_trades["rsi_at_buy"].dropna()
            if not rsi_vals.empty:
                fig_rsi = px.histogram(rsi_vals, nbins=10, title="매수 시 RSI 분포",
                                       labels={"value":"RSI","count":"건수"})
                fig_rsi.add_vline(x=rsi_threshold, line_dash="dash", line_color="orange")
                fig_rsi.update_layout(height=250)
                st.plotly_chart(fig_rsi, use_container_width=True)
        with c2:
            vix_vals = df_trades["vix_at_buy"].dropna() if "vix_at_buy" in df_trades.columns else pd.Series()
            if not vix_vals.empty:
                fig_vix = px.histogram(vix_vals, nbins=10, title="매수 시 VIX 분포",
                                       labels={"value":"VIX","count":"건수"})
                fig_vix.add_vline(x=vix_caution, line_dash="dash", line_color="orange",
                                   annotation_text="주의")
                fig_vix.add_vline(x=vix_half, line_dash="dash", line_color="red",
                                   annotation_text="공황")
                fig_vix.update_layout(height=250)
                st.plotly_chart(fig_vix, use_container_width=True)

    st.divider()

    # 포지션 청산
    st.markdown("### 💰 포지션 청산")
    open_ids = open_t["id"].tolist() if len(open_t) > 0 else []
    if open_ids:
        sel_id = st.selectbox("청산할 거래 #", open_ids,
                              format_func=lambda i: f"#{i} {df_trades[df_trades['id']==i]['티커'].values[0] if '티커' in df_trades.columns else ''}")
        orig = df_trades[df_trades["id"] == sel_id].iloc[0]
        curr_px = price_map.get(orig.get("ticker",""), orig["매수가"] if "매수가" in orig else orig["price"])
        sell_px = st.number_input("매도 가격 ($)", min_value=0.01, value=float(curr_px), step=0.01)
        if st.button("✅ 매도 기록", type="secondary"):
            for t in trades:
                if t["id"] == sel_id:
                    pnl = round((sell_px - t["price"]) * t["qty"], 2)
                    t.update({"status":"closed","sell_price":sell_px,"pnl_usd":pnl})
            save_json(TRADES_FILE, trades)
            st.success(f"청산 완료! 손익: ${pnl:+,.2f}")
            st.rerun()
    else:
        st.info("오픈 포지션이 없습니다.")

    csv = df_trades.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇ 거래 기록 CSV", csv, "paper_trades.csv", "text/csv")
