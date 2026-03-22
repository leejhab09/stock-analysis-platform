"""
포트폴리오 최적화 페이지
- 섹터별 종목 유니버스 (100+ 종목)
- Markowitz / Min Variance / Risk Parity
- 모멘텀 필터 기반 1개월 유망 포트폴리오
- Walk-forward 백테스트
- 매일 자동 분석 & 히스토리 비교
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date, timedelta

from utils.stock_data import get_price_history, get_usd_krw
from utils.optimizer import (
    optimize, walkforward_backtest, efficient_frontier,
    compute_returns, portfolio_stats, momentum_score
)
from utils.universe import UNIVERSE, SP500_TOP30, NASDAQ_TOP20, MOMENTUM_UNIVERSE
from utils.daily_runner import (
    run_daily_analysis, load_daily, list_daily_dates, daily_result_path
)

st.set_page_config(page_title="포트폴리오 최적화 | 해외주식", layout="wide")

# ── 자동 새로고침 (1시간마다)
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 60 * 1000, key="auto_refresh")
except Exception:
    pass

st.markdown("<h2 style='color:#1a56db;margin-bottom:4px;'>🧮 포트폴리오 최적화</h2>",
            unsafe_allow_html=True)
st.markdown(
    "<p style='color:#666;font-size:.85rem;margin-bottom:4px;'>"
    "Markowitz MPT · Risk Parity · 모멘텀 필터 · Walk-forward 백테스트 · 매일 자동 분석</p>",
    unsafe_allow_html=True)
st.warning("⚠️ 본 분석은 과거 데이터 기반 참고 자료입니다. 투자 결정의 책임은 투자자 본인에게 있습니다.", icon="⚠️")

MODEL_LABELS = {
    "max_sharpe":   "📈 Max Sharpe",
    "min_variance": "🛡️ Min Variance",
    "risk_parity":  "⚖️ Risk Parity",
    "equal_weight": "📊 Equal Weight",
}

# ══════════════════════════════════════════
# 사이드바 — 종목 유니버스 & 설정
# ══════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📦 종목 유니버스")

    # 프리셋 버튼
    preset = st.selectbox("빠른 프리셋", [
        "직접 선택",
        "🚀 모멘텀 유니버스 (20종목)",
        "🇺🇸 S&P 500 TOP 30",
        "💻 나스닥 TOP 20",
    ])

    if preset == "🚀 모멘텀 유니버스 (20종목)":
        preset_tickers = MOMENTUM_UNIVERSE
    elif preset == "🇺🇸 S&P 500 TOP 30":
        preset_tickers = SP500_TOP30
    elif preset == "💻 나스닥 TOP 20":
        preset_tickers = NASDAQ_TOP20
    else:
        preset_tickers = None

    # 섹터 선택
    st.markdown("**섹터별 종목 추가**")
    sector_sel = st.multiselect(
        "섹터 선택 (중복 가능)",
        list(UNIVERSE.keys()),
        default=[],
        help="섹터를 선택하면 해당 종목이 자동 추가됩니다."
    )

    sector_tickers = []
    for s in sector_sel:
        sector_tickers += UNIVERSE[s]["tickers"]
        with st.expander(f"{s} ({len(UNIVERSE[s]['tickers'])}종목)", expanded=False):
            st.caption(UNIVERSE[s]["desc"])
            st.write(", ".join(UNIVERSE[s]["tickers"]))

    # 직접 입력
    st.markdown("**직접 추가 (쉼표 구분)**")
    manual_input = st.text_input("추가 티커", placeholder="예: AAPL,TSLA,NVDA")
    manual_tickers = [t.strip().upper() for t in manual_input.split(",") if t.strip()]

    # 최종 유니버스 합산
    if preset_tickers:
        base = preset_tickers
    else:
        base = []
    all_selected = list(dict.fromkeys(base + sector_tickers + manual_tickers))
    if not all_selected:
        all_selected = MOMENTUM_UNIVERSE  # fallback

    st.info(f"총 **{len(all_selected)}개** 종목 선택됨")
    with st.expander("선택된 종목 목록"):
        st.write(", ".join(all_selected))

    st.markdown("---")
    st.markdown("### ⚙️ 최적화 설정")

    period = st.selectbox("데이터 기간", ["1y", "2y", "3y"], index=1,
                          format_func=lambda x: {"1y":"1년","2y":"2년","3y":"3년"}[x])
    model = st.selectbox("최적화 모델", list(MODEL_LABELS.keys()),
                         format_func=lambda x: MODEL_LABELS[x])
    use_momentum = st.checkbox("모멘텀 필터 적용", value=True)
    top_n = st.slider("모멘텀 상위 종목 수", 3, min(len(all_selected), 15),
                      min(8, len(all_selected)))
    train_m = st.slider("백테스트 학습 기간(개월)", 3, 12, 6)
    test_m  = st.slider("백테스트 평가 기간(개월)", 1, 3, 1)

    st.markdown("---")
    run_btn   = st.button("🚀 지금 분석 실행", use_container_width=True, type="primary")
    daily_btn = st.button("📅 오늘 일일 분석 저장", use_container_width=True)

# ── 일일 분석 저장 버튼
if daily_btn:
    with st.spinner("일일 분석 실행 중..."):
        dr = run_daily_analysis(
            tickers=all_selected, model=model,
            period=period, top_n=top_n, force=True
        )
    if dr:
        st.success(f"✅ {dr['date']} 일일 분석 저장 완료 — {len(dr['weights'])}개 종목 선정")
    else:
        st.error("분석 실패. 종목을 확인하세요.")

# ══════════════════════════════════════════
# 메인 탭
# ══════════════════════════════════════════
tab_daily, tab_opt, tab_bt, tab_ef, tab_mom = st.tabs([
    "📅 일일 분석 현황",
    "🎯 최적 포트폴리오",
    "📉 백테스트",
    "🌐 효율적 프론티어",
    "🚀 1개월 유망 포트폴리오",
])

# ─────────────────────────────────────────
# TAB 0 : 일일 분석 현황
# ─────────────────────────────────────────
with tab_daily:
    st.markdown("### 📅 일일 자동 분석 현황")

    dates_list = list_daily_dates()

    if not dates_list:
        st.info("아직 일일 분석 결과가 없습니다. 사이드바의 '오늘 일일 분석 저장' 버튼을 클릭하세요.")
    else:
        today_data = load_daily(date.today())
        yest_data  = {}
        if len(dates_list) >= 2:
            try:
                yest_data = load_daily(date.fromisoformat(dates_list[1]))
            except Exception:
                pass

        # 최신 분석 KPI
        if today_data:
            st.markdown(f"**최신 분석: {today_data.get('date')}  "
                        f"<span style='color:#888;font-size:.82rem;'>"
                        f"업데이트: {today_data.get('timestamp','')[:16]}</span>**",
                        unsafe_allow_html=True)
            k1, k2, k3, k4 = st.columns(4)
            stats = today_data.get("stats", {})
            k1.metric("선정 종목 수", f"{len(today_data.get('weights',{}))}개")
            k2.metric("예상 연간수익률", f"{stats.get('annual_return',0)*100:.2f}%")
            k3.metric("샤프비율", f"{stats.get('sharpe',0):.2f}")
            k4.metric("연간 변동성", f"{stats.get('annual_volatility',0)*100:.2f}%")
        else:
            st.info(f"오늘({date.today()}) 분석 결과 없음. 사이드바에서 '오늘 일일 분석 저장'을 클릭하세요.")

        # 오늘 vs 어제 비중 비교
        if today_data and yest_data:
            st.markdown("---")
            st.markdown("**오늘 vs 어제 포트폴리오 비교**")
            today_w = today_data.get("weights", {})
            yest_w  = yest_data.get("weights", {})
            all_t   = list(dict.fromkeys(list(today_w.keys()) + list(yest_w.keys())))
            cmp_df = pd.DataFrame({
                "종목": all_t,
                f"오늘({today_data.get('date','')}) %": [round(today_w.get(t, 0)*100, 1) for t in all_t],
                f"어제({yest_data.get('date','')}) %":  [round(yest_w.get(t, 0)*100, 1) for t in all_t],
            })
            cmp_df["변화"] = cmp_df.iloc[:, 1] - cmp_df.iloc[:, 2]
            cmp_df["변화"] = cmp_df["변화"].apply(lambda x: f"{x:+.1f}%")
            st.dataframe(cmp_df, use_container_width=True, hide_index=True)

        # 히스토리 테이블
        st.markdown("---")
        st.markdown(f"**일일 분석 히스토리** (총 {len(dates_list)}일)")
        hist_rows = []
        for d_str in dates_list[:30]:
            try:
                dd = load_daily(date.fromisoformat(d_str))
                if not dd:
                    continue
                top3 = sorted(dd.get("weights", {}).items(), key=lambda x: -x[1])[:3]
                hist_rows.append({
                    "날짜": d_str,
                    "모델": dd.get("model", ""),
                    "선정 종목": ", ".join([f"{t}({w*100:.0f}%)" for t, w in top3]),
                    "샤프": f"{dd.get('stats',{}).get('sharpe',0):.2f}",
                    "연간수익률": f"{dd.get('stats',{}).get('annual_return',0)*100:.2f}%",
                    "변동성": f"{dd.get('stats',{}).get('annual_volatility',0)*100:.2f}%",
                })
            except Exception:
                continue
        if hist_rows:
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True,
                         hide_index=True, height=350)

        # 샤프비율 추이 차트
        if len(hist_rows) > 1:
            st.markdown("**샤프비율 추이**")
            fig_h = go.Figure(go.Scatter(
                x=[r["날짜"] for r in hist_rows[::-1]],
                y=[float(r["샤프"]) for r in hist_rows[::-1]],
                mode="lines+markers",
                line=dict(color="#1a56db", width=2),
                marker=dict(size=6),
            ))
            fig_h.update_layout(height=220, margin=dict(l=0, r=0, t=20, b=0),
                                 yaxis_title="샤프비율")
            st.plotly_chart(fig_h, use_container_width=True)

# ── 분석 실행 (탭 1~4 공통 데이터)
if run_btn or "opt_result" not in st.session_state:
    if not run_btn and "opt_result" in st.session_state:
        pass
    else:
        with st.spinner(f"{len(all_selected)}개 종목 데이터 수집 중..."):
            price_data = {}
            for t in all_selected:
                h = get_price_history(t, period=period)
                if not h.empty:
                    price_data[t] = h["Close"]
            if len(price_data) < 2:
                st.error("유효 종목이 2개 미만입니다.")
                st.stop()
            prices = pd.DataFrame(price_data).dropna()

        with st.spinner("최적화 계산 중..."):
            opt_res = optimize(prices, model=model,
                               apply_momentum_filter=use_momentum, top_n=top_n)
        with st.spinner("백테스트 진행 중..."):
            bt_res = walkforward_backtest(
                prices, model=model,
                train_months=train_m, test_months=test_m,
                apply_momentum=use_momentum
            )
        st.session_state.update({
            "opt_result": opt_res, "bt_result": bt_res,
            "prices": prices, "model_name": model
        })

if "opt_result" not in st.session_state:
    for tab in [tab_opt, tab_bt, tab_ef, tab_mom]:
        with tab:
            st.info("사이드바에서 '지금 분석 실행'을 클릭하세요.")
    st.stop()

opt_res  = st.session_state["opt_result"]
bt_res   = st.session_state["bt_result"]
prices   = st.session_state["prices"]
model_nm = st.session_state.get("model_name", model)

# ─────────────────────────────────────────
# TAB 1 : 최적 포트폴리오
# ─────────────────────────────────────────
with tab_opt:
    weights = opt_res["weights"]
    stats   = opt_res["stats"]

    st.markdown(f"#### {MODEL_LABELS.get(model_nm, model_nm)} 최적 포트폴리오")
    st.caption(f"유니버스 {len(prices.columns)}종목 → {len(weights)}종목 선정")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("연간 기대수익률", f"{stats['annual_return']*100:.2f}%")
    k2.metric("연간 변동성",     f"{stats['annual_volatility']*100:.2f}%")
    k3.metric("샤프비율",        f"{stats['sharpe']:.2f}")
    k4.metric("편입 종목 수",    f"{len(weights)}개")

    c1, c2 = st.columns([5, 5])
    with c1:
        w_df = pd.DataFrame([
            {"종목": t, "비중(%)": round(w*100, 2)}
            for t, w in sorted(weights.items(), key=lambda x: -x[1])
        ])
        st.dataframe(
            w_df.style.bar(subset=["비중(%)"], color="#1a56db"),
            use_container_width=True, hide_index=True
        )
    with c2:
        fig_pie = go.Figure(go.Pie(
            labels=list(weights.keys()),
            values=[round(v*100, 2) for v in weights.values()],
            hole=0.4, textinfo="label+percent",
            marker_colors=px.colors.qualitative.Set2,
        ))
        fig_pie.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0),
                               showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    # 모멘텀 점수
    if "momentum_scores" in opt_res and not opt_res["momentum_scores"].empty:
        st.markdown("---")
        st.markdown("**전체 유니버스 모멘텀 점수**")
        mom = opt_res["momentum_scores"].sort_values(ascending=False)
        mom_df = pd.DataFrame({
            "종목": mom.index,
            "모멘텀 점수(%)": (mom.values * 100).round(2),
            "선택여부": ["✅ 편입" if t in weights else "—" for t in mom.index]
        })
        def color_mom(val):
            try:
                return "color:green;font-weight:700" if float(val) > 0 else "color:red"
            except Exception:
                return ""
        try:
            st.dataframe(mom_df.style.map(color_mom, subset=["모멘텀 점수(%)"]),
                         use_container_width=True, hide_index=True, height=300)
        except AttributeError:
            st.dataframe(mom_df.style.applymap(color_mom, subset=["모멘텀 점수(%)"]),
                         use_container_width=True, hide_index=True, height=300)

# ─────────────────────────────────────────
# TAB 2 : 백테스트
# ─────────────────────────────────────────
with tab_bt:
    st.markdown(f"#### Walk-Forward 백테스트 "
                f"<span style='font-size:.85rem;color:#888;font-weight:400;'>"
                f"학습 {train_m}개월 → 평가 {test_m}개월 반복</span>",
                unsafe_allow_html=True)

    metrics = bt_res["metrics"]
    m_labels = {
        "포트폴리오_연간수익률": "연간수익률",
        "포트폴리오_연간변동성": "연간변동성",
        "포트폴리오_샤프비율":   "샤프비율",
        "포트폴리오_최대낙폭":   "최대낙폭(MDD)",
        "포트폴리오_소르티노":   "소르티노비율",
        "포트폴리오_칼마비율":   "칼마비율",
    }
    rows = []
    for k, label in m_labels.items():
        bk = k.replace("포트폴리오", "벤치마크")
        rows.append({
            "지표": label,
            MODEL_LABELS.get(model_nm, model_nm): metrics.get(k, "N/A"),
            "벤치마크(동일비중)": metrics.get(bk, "N/A"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 누적 수익률 차트
    fig_bt_c = go.Figure()
    port_c  = bt_res["portfolio_curve"]
    bench_c = bt_res["benchmark_curve"]
    fig_bt_c.add_trace(go.Scatter(x=port_c.index, y=port_c.values,
                                   name=MODEL_LABELS.get(model_nm, model_nm),
                                   line=dict(color="#1a56db", width=2.5)))
    fig_bt_c.add_trace(go.Scatter(x=bench_c.index, y=bench_c.values,
                                   name="벤치마크(동일비중)",
                                   line=dict(color="#94a3b8", width=1.5, dash="dash")))
    fig_bt_c.update_layout(height=380, yaxis_title="누적 수익률(시작=1.0)",
                            legend=dict(orientation="h", y=1.05),
                            margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_bt_c, use_container_width=True)

    # MDD 차트
    port_r   = bt_res["port_returns"]
    cum      = (1 + port_r).cumprod()
    drawdown = (cum / cum.cummax() - 1) * 100
    fig_dd = go.Figure(go.Scatter(
        x=drawdown.index, y=drawdown.values, fill="tozeroy",
        line=dict(color="#ef4444", width=1), fillcolor="rgba(239,68,68,0.2)", name="낙폭(%)"))
    fig_dd.update_layout(height=200, title="낙폭(Drawdown %)",
                          yaxis_title="%", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_dd, use_container_width=True)

    if bt_res["history"]:
        st.markdown("**리밸런싱 이력**")
        hist_rows = []
        for h in bt_res["history"]:
            top3 = sorted(h["weights"].items(), key=lambda x: -x[1])[:3]
            hist_rows.append({
                "날짜": str(h["date"]),
                "상위 3종목": ", ".join([f"{t}({w*100:.0f}%)" for t, w in top3]),
                "샤프(학습)": f"{h['sharpe']:.2f}",
            })
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True,
                     hide_index=True, height=200)

# ─────────────────────────────────────────
# TAB 3 : 효율적 프론티어
# ─────────────────────────────────────────
with tab_ef:
    st.markdown("#### 효율적 프론티어 (Monte Carlo 5,000 시뮬레이션)")
    ret_df = compute_returns(prices)
    mean_r = ret_df.mean().values
    cov_m  = ret_df.cov().values

    with st.spinner("계산 중..."):
        ef_df = efficient_frontier(mean_r, cov_m, n_points=60)

    fig_ef = go.Figure()
    fig_ef.add_trace(go.Scatter(
        x=ef_df["volatility"]*100, y=ef_df["return"]*100,
        mode="markers",
        marker=dict(color=ef_df["sharpe"], colorscale="Viridis",
                    size=4, opacity=0.5,
                    colorbar=dict(title="Sharpe")),
        name="랜덤 포트폴리오",
        hovertemplate="변동성: %{x:.1f}%<br>수익률: %{y:.1f}%<extra></extra>"
    ))
    s = opt_res["stats"]
    fig_ef.add_trace(go.Scatter(
        x=[s["annual_volatility"]*100], y=[s["annual_return"]*100],
        mode="markers+text",
        marker=dict(color="#ef4444", size=14, symbol="star"),
        text=[f"★ {MODEL_LABELS.get(model_nm, model_nm)}"],
        textposition="top center", name="현재 최적"
    ))
    fig_ef.update_layout(height=450, xaxis_title="연간 변동성(%)",
                          yaxis_title="연간 기대수익률(%)",
                          margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_ef, use_container_width=True)
    st.caption("색상이 밝을수록 샤프비율 높음. ★ = 현재 최적 포트폴리오")

# ─────────────────────────────────────────
# TAB 4 : 1개월 유망 포트폴리오
# ─────────────────────────────────────────
with tab_mom:
    st.markdown("#### 🚀 향후 1개월 유망 포트폴리오")
    st.markdown(
        "<div style='background:#EBF5FB;border-left:4px solid #1a56db;"
        "padding:10px 14px;border-radius:5px;font-size:.85rem;color:#1a3c6e;'>"
        "듀얼 모멘텀(1M·3M·6M) 상위 종목 → Max Sharpe 최적화<br>"
        "<b>매월 리밸런싱 권장</b>"
        "</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    mom_all = momentum_score(prices)
    mom_pos = mom_all[mom_all > 0].sort_values(ascending=False)

    if len(mom_pos) < 2:
        st.warning("모멘텀 양수 종목 부족. 후보 종목을 늘려주세요.")
    else:
        sel_n    = min(top_n, len(mom_pos))
        selected = mom_pos.head(sel_n).index.tolist()
        sel_prices = prices[selected]

        from utils.optimizer import max_sharpe
        try:
            ret_s = compute_returns(sel_prices)
            mr    = ret_s.mean().values
            cv    = ret_s.cov().values
            w_opt = max_sharpe(mr, cv, len(selected))
            w_dict = dict(zip(selected, w_opt))
            r, v, s = portfolio_stats(w_opt, mr, cv)
        except Exception as e:
            st.error(f"최적화 실패: {e}")
            st.stop()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("선별 종목", f"{len(selected)}개",
                  f"전체 {len(prices.columns)}개 중")
        k2.metric("예상 연간수익률", f"{r*100:.2f}%")
        k3.metric("샤프비율", f"{s:.2f}")
        k4.metric("연간 변동성", f"{v*100:.2f}%")

        # 결과 테이블
        n21  = min(21, len(prices))
        n63  = min(63, len(prices))
        n126 = min(126, len(prices))
        result_df = pd.DataFrame({
            "종목": selected,
            "1M(%)":    [round(float(prices[t].iloc[-1]/prices[t].iloc[-n21] -1)*100, 2) for t in selected],
            "3M(%)":    [round(float(prices[t].iloc[-1]/prices[t].iloc[-n63] -1)*100, 2) for t in selected],
            "6M(%)":    [round(float(prices[t].iloc[-1]/prices[t].iloc[-n126]-1)*100, 2) for t in selected],
            "모멘텀점수": [round(float(mom_pos[t])*100, 2) for t in selected],
            "최적비중(%)": [round(w_dict[t]*100, 2) for t in selected],
        }).sort_values("최적비중(%)", ascending=False)

        def color_ret(val):
            try:
                return "color:#ef4444;font-weight:700" if float(val) > 0 else "color:#3b82f6"
            except Exception:
                return ""
        try:
            styled_r = result_df.style.map(color_ret, subset=["1M(%)","3M(%)","6M(%)","모멘텀점수"])
        except AttributeError:
            styled_r = result_df.style.applymap(color_ret, subset=["1M(%)","3M(%)","6M(%)","모멘텀점수"])
        st.dataframe(styled_r, use_container_width=True, hide_index=True)

        # 비중 바 차트
        fig_w = go.Figure(go.Bar(
            x=result_df["종목"], y=result_df["최적비중(%)"],
            marker_color="#1a56db",
            text=result_df["최적비중(%)"].apply(lambda x: f"{x:.1f}%"),
            textposition="outside",
        ))
        fig_w.update_layout(height=300, yaxis_title="비중(%)",
                             margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
        st.plotly_chart(fig_w, use_container_width=True)

        # 투자 금액 계산기
        st.markdown("---")
        st.markdown("**💰 투자 금액 계산기**")
        fx = get_usd_krw()
        invest_usd = st.number_input("투자 금액 (USD)", min_value=100, value=10000, step=500)
        alloc_df = pd.DataFrame({
            "종목": list(w_dict.keys()),
            "비중(%)": [round(v*100, 1) for v in w_dict.values()],
            "금액(USD)": [f"${v*invest_usd:,.0f}" for v in w_dict.values()],
            "금액(KRW)": [f"₩{v*invest_usd*fx:,.0f}" for v in w_dict.values()],
        }).sort_values("비중(%)", ascending=False)
        st.dataframe(alloc_df, use_container_width=True, hide_index=True)

        st.markdown("**투자 실행 체크리스트**")
        st.markdown("""
- [ ] 현재 포트폴리오와 목표 비중 차이 확인
- [ ] 환율 확인 후 투자 금액 환산
- [ ] 분할 매수 (1~2주에 걸쳐 진입) 고려
- [ ] 1개월 후 모멘텀 재계산 → 리밸런싱
- [ ] 손절 기준 사전 설정 (예: 개별 종목 -8% 이하 시 재검토)
        """)
