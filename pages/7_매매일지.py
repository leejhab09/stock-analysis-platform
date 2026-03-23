"""
매매 일지 — auto_trader.py 가 기록한 일지를 실시간 표시
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import date, timedelta, datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="매매 일지 | 해외주식", layout="wide")
st_autorefresh(interval=30000)  # 30초마다 자동 갱신

DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")
TRADES_FILE = os.path.join(DATA_DIR, "paper_trades.json")
LOG_FILE    = os.path.join(DATA_DIR, "auto_trader.log")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("<h2 style='color:#333;'>📓 페이퍼 매매 통합 일지</h2>", unsafe_allow_html=True)

tab_us, tab_kr = st.tabs(["🇺🇸 미국 주식 (USD)", "🇰🇷 국내 주식 (KRW)"])

# ═══════════════════════════════════════════
# 🇺🇸 미국 탭
# ═══════════════════════════════════════════
with tab_us:
  st.markdown("""
  <div style='background:#EBF5FF;border-left:6px solid #1a56db;padding:10px 16px;
               border-radius:6px;margin-bottom:12px;'>
  🇺🇸 <b style='color:#1a56db;'>미국 주식 페이퍼 매매 일지</b>
   · 통화: USD · 장시간: ET 09:30~16:00 (KST 22:30~05:00) · 자동트레이더: auto_trader.py
  </div>""", unsafe_allow_html=True)

st.caption("auto_trader.py 자동 기록 · 30초마다 갱신")

# ── 트레이더 상태 확인 ────────────────────────────────────────
col_s1, col_s2, col_s3 = st.columns(3)

# 마지막 로그 시간으로 실행 여부 확인
if os.path.exists(LOG_FILE):
    mtime = os.path.getmtime(LOG_FILE)
    last_log = datetime.fromtimestamp(mtime)
    diff_min = (datetime.now() - last_log).seconds // 60
    if diff_min < 10:
        col_s1.success(f"🟢 트레이더 실행 중\n마지막 활동: {diff_min}분 전")
    else:
        col_s1.error(f"🔴 트레이더 비활성\n마지막: {last_log.strftime('%m/%d %H:%M')}")
else:
    col_s1.warning("⚠️ 트레이더 미시작")
    col_s2.info("**시작 방법:**\n```\npython3 auto_trader.py &\n```")

# ── 날짜 선택 ─────────────────────────────────────────────────
st.divider()

# 일지 파일 목록
journal_files = sorted([
    f.replace(".json", "") for f in os.listdir(JOURNAL_DIR)
    if f.endswith(".json")
], reverse=True) if os.path.exists(JOURNAL_DIR) else []

if not journal_files:
    st.info("아직 일지가 없습니다. auto_trader.py 를 실행하면 자동으로 기록됩니다.")
    st.code("cd ~/stock-analysis-platform && python3 auto_trader.py &")
    st.stop()

selected_date = st.selectbox(
    "📅 날짜 선택",
    journal_files,
    format_func=lambda d: f"{d} {'(오늘)' if d == date.today().isoformat() else ''}"
)

journal = load_json(os.path.join(JOURNAL_DIR, f"{selected_date}.json"), {})
if not journal:
    st.warning("해당 날짜 일지 없음")
    st.stop()

summary = journal.get("summary", {})
scans   = journal.get("scans",  [])
jtrades = journal.get("trades", [])

# ── 당일 요약 KPI ─────────────────────────────────────────────
st.subheader(f"📋 {selected_date} 요약")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("총 스캔",    f"{summary.get('total_scans', 0)}회")
k2.metric("자동 매수",  f"{summary.get('total_trades', 0)}건")
k3.metric("투자금",     f"${summary.get('total_invested', 0):,.0f}")
k4.metric("매수 종목",  ", ".join(summary.get("tickers_traded", [])) or "없음")
k5.metric("마지막 갱신", summary.get("last_updated", "-")[-8:] if summary.get("last_updated") else "-")

st.divider()

# ── 당일 매매 기록 ────────────────────────────────────────────
st.subheader("🛒 당일 자동 매수 내역")
if not jtrades:
    st.info("당일 매수 없음 — 조건 미충족 또는 장외 시간")
else:
    df_jt = pd.DataFrame(jtrades)
    disp_cols = {
        "time":"시간", "ticker":"티커", "name":"종목명",
        "price":"매수가($)", "qty":"수량", "amount_usd":"금액($)",
        "rsi":"RSI", "change_pct":"낙폭(%)", "drop_52w":"52주낙폭(%)",
        "vix":"VIX", "vix_status":"VIX상태", "reason":"매수이유"
    }
    show = {k:v for k,v in disp_cols.items() if k in df_jt.columns}
    st.dataframe(
        df_jt[list(show.keys())].rename(columns=show),
        use_container_width=True, hide_index=True
    )

    # 매수 시점 상세
    for t in jtrades:
        with st.expander(f"📌 {t['time']} | {t['ticker']} ${t['price']:.2f} × {t['qty']}주 = ${t['amount_usd']:.0f}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                | 항목 | 값 |
                |------|-----|
                | 티커 | **{t['ticker']}** |
                | 종목명 | {t.get('name','-')} |
                | 매수가 | ${t['price']:.2f} |
                | 수량 | {t['qty']}주 |
                | 금액 | ${t['amount_usd']:.0f} |
                | VIX | {t.get('vix','-')} ({t.get('vix_status','-')}) |
                """)
            with c2:
                st.markdown("**조건 충족 내역**")
                conds = t.get("conditions", {})
                for cname, desc in conds.items():
                    st.markdown(f"✅ **{cname}**: {desc}")
                st.markdown(f"**매수 이유**: {t.get('reason','-')}")

st.divider()

# ── 스캔 타임라인 ─────────────────────────────────────────────
st.subheader("🔍 스캔 타임라인")
market_scans = [s for s in scans if s.get("status") == "장중"]
offhour_scans = [s for s in scans if s.get("status") != "장중"]

col1, col2 = st.columns([2,1])
with col1:
    if market_scans:
        timeline_data = []
        for s in market_scans:
            n_signals = len(s.get("signals", []))
            timeline_data.append({
                "시간": s["time"],
                "신호수": n_signals,
                "VIX": s.get("vix", 0),
                "상태": "신호발생" if n_signals > 0 else "신호없음"
            })
        df_tl = pd.DataFrame(timeline_data)
        fig_tl = go.Figure()
        fig_tl.add_trace(go.Scatter(
            x=df_tl["시간"], y=df_tl["신호수"],
            mode="lines+markers",
            marker=dict(
                size=12,
                color=["#16a34a" if n > 0 else "#94a3b8" for n in df_tl["신호수"]],
                symbol=["star" if n > 0 else "circle" for n in df_tl["신호수"]],
            ),
            line=dict(color="#cbd5e1"),
            hovertemplate="<b>%{x}</b><br>신호: %{y}개<extra></extra>",
        ))
        fig_tl.update_layout(
            title="장중 스캔별 신호 발생 횟수",
            xaxis_title="시간", yaxis_title="신호 수",
            height=280, plot_bgcolor="white",
            yaxis=dict(gridcolor="#f0f0f0", tickformat="d"),
        )
        st.plotly_chart(fig_tl, use_container_width=True)
    else:
        st.info("장중 스캔 기록 없음")

with col2:
    st.metric("장중 스캔", f"{len(market_scans)}회")
    st.metric("장외 스캔", f"{len(offhour_scans)}회")
    if market_scans:
        total_signals = sum(len(s.get("signals",[])) for s in market_scans)
        st.metric("총 신호 발생", f"{total_signals}회")

# 신호 발생 종목 상세
all_signals = []
for s in market_scans:
    for sig in s.get("signals", []):
        sig["scan_time"] = s["time"]
        all_signals.append(sig)

if all_signals:
    st.markdown("**신호 발생 종목 상세**")
    df_sig = pd.DataFrame(all_signals)
    st.dataframe(df_sig, use_container_width=True, hide_index=True, height=200)

st.divider()

# ── 전체 거래 누적 성과 ───────────────────────────────────────
st.subheader("📈 전체 누적 성과")
all_trades = load_json(TRADES_FILE, [])

if not all_trades:
    st.info("거래 기록 없음")
else:
    import yfinance as yf

    @st.cache_data(ttl=300)
    def get_current_prices(tickers):
        prices = {}
        for t in tickers:
            try:
                hist = yf.Ticker(t).history(period="2d")
                if not hist.empty:
                    prices[t] = round(float(hist["Close"].iloc[-1]), 2)
            except: pass
        return prices

    open_trades   = [t for t in all_trades if t.get("status") == "open"]
    closed_trades = [t for t in all_trades if t.get("status") == "closed"]
    tickers       = list({t["ticker"] for t in open_trades})
    curr_prices   = get_current_prices(tickers) if tickers else {}

    for t in open_trades:
        cp = curr_prices.get(t["ticker"])
        t["curr_price"] = cp
        t["pnl_unrealized"] = round((cp - t["price"]) * t["qty"], 2) if cp else None

    total_invested  = sum(t["price"] * t["qty"] for t in open_trades)
    total_unrealized = sum(t["pnl_unrealized"] for t in open_trades if t["pnl_unrealized"])
    total_realized   = sum(t.get("pnl_usd", 0) or 0 for t in closed_trades)
    total_pnl        = total_unrealized + total_realized

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 거래",      f"{len(all_trades)}건 ({len(open_trades)}오픈)")
    k2.metric("총 투자금",    f"${total_invested:,.0f}")
    k3.metric("미실현 손익",  f"${total_unrealized:+,.0f}",
              delta=f"{total_unrealized/total_invested*100:+.2f}%" if total_invested > 0 else None)
    k4.metric("실현 손익",    f"${total_realized:+,.0f}")

    # 날짜별 거래 건수 차트
    if len(all_trades) > 1:
        df_all = pd.DataFrame(all_trades)
        df_all["date"] = pd.to_datetime(df_all["date"]).dt.date.astype(str)
        daily_count = df_all.groupby("date").size().reset_index(name="거래수")

        col1, col2 = st.columns(2)
        with col1:
            fig_dc = px.bar(daily_count, x="date", y="거래수",
                            title="날짜별 자동 매수 건수",
                            color="거래수", color_continuous_scale="Blues")
            fig_dc.update_layout(height=280, coloraxis_showscale=False)
            st.plotly_chart(fig_dc, use_container_width=True)

        with col2:
            # 종목별 매수 횟수
            ticker_count = df_all.groupby("ticker").size().reset_index(name="매수횟수")
            fig_tc = px.pie(ticker_count, values="매수횟수", names="ticker",
                            title="종목별 매수 비중",
                            color_discrete_sequence=px.colors.qualitative.Set2)
            fig_tc.update_layout(height=280)
            st.plotly_chart(fig_tc, use_container_width=True)

st.divider()

# ── 최근 로그 ─────────────────────────────────────────────────
st.subheader("🖥️ 트레이더 로그 (최근 30줄)")
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    recent = "".join(lines[-30:])
    st.code(recent, language="text")
else:
    st.info("로그 파일 없음 — auto_trader.py 를 먼저 실행하세요")
    st.code("cd ~/stock-analysis-platform && python3 auto_trader.py &")

# ═══════════════════════════════════════════
# 🇰🇷 국내 탭
# ═══════════════════════════════════════════
with tab_kr:
    st.markdown("""
    <div style='background:#FFF0F0;border-left:6px solid #c0392b;padding:10px 16px;
                 border-radius:6px;margin-bottom:12px;'>
    🇰🇷 <b style='color:#c0392b;'>국내 주식 페이퍼 매매 일지</b>
     · 통화: KRW · 장시간: KST 09:00~15:30 · 자동트레이더: auto_trader_kr.py
    </div>""", unsafe_allow_html=True)

    KR_LOG_FILE    = os.path.join(DATA_DIR, "auto_trader_kr.log")
    KR_TRADES_FILE = os.path.join(DATA_DIR, "kr_paper_trades.json")
    KR_JOURNAL_DIR = JOURNAL_DIR

    # 트레이더 상태
    if os.path.exists(KR_LOG_FILE):
        mtime_kr   = os.path.getmtime(KR_LOG_FILE)
        last_kr    = datetime.fromtimestamp(mtime_kr)
        diff_kr    = (datetime.now() - last_kr).seconds // 60
        if diff_kr < 10:
            st.success(f"🟢 국내 트레이더 실행 중 — 마지막 활동: {diff_kr}분 전")
        else:
            st.error(f"🔴 국내 트레이더 비활성 — 마지막: {last_kr.strftime('%m/%d %H:%M')}")
    else:
        st.warning("⚠️ 국내 트레이더 미시작")
        st.code("cd ~/stock-analysis-platform && python3 auto_trader_kr.py &")

    # 날짜 선택
    kr_journals = sorted([
        f.replace("KR_","").replace(".json","")
        for f in os.listdir(KR_JOURNAL_DIR) if f.startswith("KR_") and f.endswith(".json")
    ], reverse=True) if os.path.exists(KR_JOURNAL_DIR) else []

    if not kr_journals:
        st.info("국내 일지 없음 — auto_trader_kr.py 를 실행하면 자동 기록됩니다.")
    else:
        kr_sel  = st.selectbox("📅 날짜", kr_journals,
                               format_func=lambda d: f"{d} {'(오늘)' if d == date.today().isoformat() else ''}",
                               key="kr_date")
        kr_j    = load_json(os.path.join(KR_JOURNAL_DIR, f"KR_{kr_sel}.json"), {})
        kr_sum  = kr_j.get("summary", {})
        kr_scans  = kr_j.get("scans",  [])
        kr_trades = kr_j.get("trades", [])

        st.subheader(f"📋 {kr_sel} 요약")
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("총 스캔",   f"{kr_sum.get('total_scans',0)}회")
        k2.metric("자동 매수", f"{kr_sum.get('total_trades',0)}건")
        k3.metric("투자금",    f"₩{kr_sum.get('total_invested',0):,.0f}")
        k4.metric("매수 종목", ", ".join(kr_sum.get("tickers_traded",[])) or "없음")
        k5.metric("마지막 갱신", kr_sum.get("last_updated","-")[-8:] if kr_sum.get("last_updated") else "-")

        st.divider()

        # 당일 매수 내역
        st.subheader("🛒 당일 자동 매수 내역")
        if not kr_trades:
            st.info("당일 매수 없음 — 조건 미충족 또는 장외 시간")
        else:
            df_kt = pd.DataFrame(kr_trades)
            show  = {k:v for k,v in {
                "time":"시간","ticker":"티커","name":"종목명","market":"시장",
                "price":"매수가(₩)","qty":"수량","amount_krw":"금액(₩)",
                "rsi":"RSI","change_pct":"낙폭(%)","vol_ratio":"거래량배율",
                "bb_pct":"%B","kospi":"KOSPI(%)","reason":"매수이유"
            }.items() if k in df_kt.columns}
            st.dataframe(df_kt[list(show.keys())].rename(columns=show),
                         use_container_width=True, hide_index=True)

            for t in kr_trades:
                with st.expander(f"📌 {t['time']} | {t['ticker']} ₩{t['price']:,} × {t['qty']}주 = ₩{t['amount_krw']:,}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"""
| 항목 | 값 |
|------|-----|
| 티커 | **{t['ticker']}** |
| 종목명 | {t.get('name','-')} |
| 시장 | {t.get('market','-')} |
| 매수가 | ₩{t['price']:,} |
| 수량 | {t['qty']}주 |
| 금액 | ₩{t['amount_krw']:,} |
| KOSPI | {t.get('kospi','-')} |
""")
                    with c2:
                        st.markdown("**조건 충족 내역**")
                        for cname, desc in t.get("conditions", {}).items():
                            st.markdown(f"✅ **{cname}**: {desc}")
                        st.markdown(f"**매수 이유**: {t.get('reason','-')}")

        st.divider()

        # 스캔 타임라인
        st.subheader("🔍 스캔 타임라인")
        mkt_scans = [s for s in kr_scans if s.get("status") == "장중"]
        if mkt_scans:
            tl = [{"시간":s["time"],"신호수":len(s.get("signals",[])),"KOSPI":s.get("kospi",0)} for s in mkt_scans]
            df_tl = pd.DataFrame(tl)
            fig_tl = go.Figure(go.Scatter(
                x=df_tl["시간"], y=df_tl["신호수"], mode="lines+markers",
                marker=dict(size=12,
                            color=["#c0392b" if n>0 else "#94a3b8" for n in df_tl["신호수"]],
                            symbol=["star" if n>0 else "circle" for n in df_tl["신호수"]]),
                line=dict(color="#cbd5e1"),
            ))
            fig_tl.update_layout(title="장중 스캔별 신호 발생",
                                  xaxis_title="시간", yaxis_title="신호 수",
                                  height=260, plot_bgcolor="white",
                                  yaxis=dict(gridcolor="#f0f0f0", tickformat="d"))
            st.plotly_chart(fig_tl, use_container_width=True)
        else:
            st.info("장중 스캔 기록 없음")

        st.divider()

        # 전체 누적 성과
        st.subheader("📈 전체 누적 성과")
        all_kr = load_json(KR_TRADES_FILE, [])
        if all_kr:
            df_all_kr = pd.DataFrame(all_kr)
            open_kr   = df_all_kr[df_all_kr["status"]=="open"]
            closed_kr = df_all_kr[df_all_kr["status"]=="closed"]
            inv_kr    = (open_kr["price"]*open_kr["qty"]).sum()
            real_kr   = closed_kr["pnl_krw"].dropna().sum() if "pnl_krw" in closed_kr.columns else 0
            k1,k2,k3,k4 = st.columns(4)
            k1.metric("총 거래",   f"{len(df_all_kr)}건")
            k2.metric("오픈",      f"{len(open_kr)}건")
            k3.metric("총 투자금", f"₩{inv_kr:,.0f}")
            k4.metric("실현 손익", f"₩{real_kr:+,.0f}")

            if len(df_all_kr) > 1:
                col1, col2 = st.columns(2)
                with col1:
                    ds = df_all_kr.sort_values("date").copy()
                    ds["누적"] = (ds["price"]*ds["qty"]).cumsum()
                    fig_c = px.area(ds, x="date", y="누적",
                                    title="누적 투자금 추이 (₩)",
                                    color_discrete_sequence=["#c0392b"])
                    fig_c.update_layout(height=260)
                    st.plotly_chart(fig_c, use_container_width=True)
                with col2:
                    tc = df_all_kr.groupby("ticker").size().reset_index(name="매수횟수")
                    tc["ticker"] = tc["ticker"].str.replace(".KS","").str.replace(".KQ","")
                    fig_tc = px.pie(tc, values="매수횟수", names="ticker",
                                    title="종목별 매수 비중",
                                    color_discrete_sequence=px.colors.sequential.Reds_r)
                    fig_tc.update_layout(height=260)
                    st.plotly_chart(fig_tc, use_container_width=True)

        # 국내 로그
        st.subheader("🖥️ 국내 트레이더 로그 (최근 30줄)")
        if os.path.exists(KR_LOG_FILE):
            with open(KR_LOG_FILE, encoding="utf-8") as f:
                lines = f.readlines()
            st.code("".join(lines[-30:]), language="text")
        else:
            st.info("로그 없음")
            st.code("python3 auto_trader_kr.py &")
