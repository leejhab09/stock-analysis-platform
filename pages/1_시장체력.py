"""
pages/1_시장체력.py — Market Health Dashboard
VIX 레짐 + 주요 지수 + CNN Fear & Greed + Polymarket 예측 + 뉴스 감성
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests
import json
from datetime import datetime
from utils.quant_engine import get_vix, fetch_index_prices, CHART_THEME

st.set_page_config(page_title="시장체력", page_icon="🌡️", layout="wide")
st.title("🌡️ 시장체력 (Market Health)")
st.markdown("시장의 전반적인 체력을 다각도로 분석합니다.")
st.markdown("---")

# ─── Helper: light chart layout ─────────────
def light_layout(**kwargs):
    base = dict(
        plot_bgcolor=CHART_THEME["plot_bgcolor"],
        paper_bgcolor=CHART_THEME["paper_bgcolor"],
        font=dict(color=CHART_THEME["font_color"]),
    )
    base.update(kwargs)
    return base

def ax_style():
    return dict(gridcolor=CHART_THEME["gridcolor"], zerolinecolor=CHART_THEME["zerolinecolor"])

# ─── VIX Gauge ───────────────────────────────
vix, regime, regime_color = get_vix()

col_gauge, col_regime = st.columns([1, 2])

with col_gauge:
    st.subheader("VIX 공포지수")
    if vix:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=vix,
            title={"text": "VIX", "font": {"color": "#333"}},
            number={"font": {"color": "#333"}},
            gauge={
                "axis": {"range": [0, 50], "tickwidth": 1, "tickcolor": "#555"},
                "bar":  {"color": regime_color},
                "bgcolor": "white",
                "steps": [
                    {"range": [0,  20], "color": "#D5F5E3"},
                    {"range": [20, 30], "color": "#FDEBD0"},
                    {"range": [30, 50], "color": "#FADBD8"},
                ],
                "threshold": {
                    "line":  {"color": "#555", "width": 3},
                    "thickness": 0.75,
                    "value": vix,
                },
            },
        ))
        fig_gauge.update_layout(height=300, margin=dict(t=30, b=0),
                                **light_layout())
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.error("VIX 데이터 조회 실패")

with col_regime:
    st.subheader("레짐 판단")
    if vix:
        st.markdown(f"""
        <div style='background:{regime_color}18;border-left:6px solid {regime_color};
                    padding:20px;border-radius:8px;margin-bottom:12px'>
        <h2 style='color:{regime_color};margin:0'>{regime}</h2>
        <p style='font-size:1.2em;margin-top:8px;color:#333'>VIX = <b>{vix:.2f}</b></p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("""
| VIX 구간 | 레짐 | 권장 행동 |
|----------|------|-----------|
| < 20 | 🟢 저변동 | 정상 매매 / 공격적 포지션 |
| 20 ~ 30 | 🟡 중변동 | 포지션 축소 / 신중 접근 |
| ≥ 30 | 🔴 고변동 | 현금 보유 / 스캔 비활성화 |
""")

st.markdown("---")

# ─── Index + Fear & Greed row ────────────────
st.subheader("📊 주요 지수 현황")
indices = fetch_index_prices()

# CNN Fear & Greed
fg_score = None
fg_rating = "N/A"
fg_prev_close = None
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://edition.cnn.com/markets/fear-and-greed',
    }
    r_fg = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
                        headers=headers, timeout=5)
    if r_fg.status_code == 200:
        fg_data = r_fg.json()['fear_and_greed']
        fg_score = round(float(fg_data['score']), 1)
        fg_rating = fg_data['rating'].replace('_', ' ').title()
        fg_prev_close = round(float(fg_data['previous_close']), 1)
except Exception:
    pass

# Render metrics row
metric_cols = st.columns(len(indices) + 1)
for col, (name, d) in zip(metric_cols, indices.items()):
    with col:
        st.metric(name, f"{d['price']:,.2f}", f"{d['change_pct']:+.2f}%")

with metric_cols[-1]:
    if fg_score is not None:
        delta_fg = f"{fg_score - fg_prev_close:+.1f}" if fg_prev_close else None
        fg_color = ("#CC0000" if fg_score < 25 else
                    "#FF8C00" if fg_score < 45 else
                    "#888888" if fg_score < 55 else
                    "#00AA44" if fg_score < 75 else "#006622")
        st.metric("😨 Fear & Greed", f"{fg_score} / 100", delta_fg)
        st.markdown(f"<small style='color:{fg_color}'><b>{fg_rating}</b></small>",
                    unsafe_allow_html=True)
    else:
        st.metric("😨 Fear & Greed", "N/A")

st.markdown("---")

# ─── VIX 3개월 차트 ──────────────────────────
st.subheader("📉 VIX 3개월 추이")
try:
    vix_hist = yf.Ticker("^VIX").history(period="3mo")
    if not vix_hist.empty:
        fig_vix = go.Figure()
        fig_vix.add_trace(go.Scatter(
            x=vix_hist.index, y=vix_hist['Close'],
            mode='lines', name='VIX',
            line=dict(color='#E74C3C', width=2),
            fill='tozeroy', fillcolor='rgba(231,76,60,0.08)',
        ))
        fig_vix.add_hline(y=20, line_dash="dash", line_color="#F39C12", line_width=1,
                          annotation_text="20 신중", annotation_position="right",
                          annotation_font_color="#F39C12")
        fig_vix.add_hline(y=30, line_dash="dash", line_color="#E74C3C", line_width=1,
                          annotation_text="30 현금", annotation_position="right",
                          annotation_font_color="#E74C3C")
        fig_vix.update_layout(
            height=280, showlegend=False,
            margin=dict(t=10, b=10), yaxis_title="VIX",
            xaxis=ax_style(), yaxis=ax_style(),
            **light_layout()
        )
        st.plotly_chart(fig_vix, use_container_width=True)
except Exception as e:
    st.warning(f"VIX 차트 로드 실패: {e}")

st.markdown("---")

# ─── Polymarket 경제 예측 ────────────────────
st.subheader("🔮 Polymarket — 경제 예측 시장")
st.caption("Polymarket 크라우드소싱 예측 확률 (실시간 데이터)")

@st.cache_data(ttl=600)
def get_polymarket_economic() -> list[dict]:
    """Polymarket에서 경제 관련 활성 마켓 가져오기"""
    economic_kw = [
        'fed rate', 'recession', 'inflation', 'gdp', 'unemployment',
        'interest rate', 'fomc', 'rate cut', 'rate hike', 'fed emergency',
        'tariff', 'trade war', 'dollar', 'oil price', 'gold price',
        's&p 500', 'nasdaq', 'stock market crash', 'crypto', 'bitcoin price',
        'federal reserve', 'powell', 'treasury',
    ]
    found = []
    try:
        for offset in range(0, 2000, 100):
            r = requests.get(
                f'https://gamma-api.polymarket.com/markets?closed=false&limit=100&offset={offset}',
                timeout=6
            )
            data = r.json()
            if not data:
                break
            for m in data:
                q = m.get('question', '').lower()
                if any(kw in q for kw in economic_kw):
                    prices_raw = m.get('outcomePrices', '[]')
                    outcomes_raw = m.get('outcomes', '[]')
                    try:
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                        yes_idx = next((i for i, o in enumerate(outcomes) if 'yes' in str(o).lower()), 0)
                        p = float(prices[yes_idx]) if prices else 0
                    except Exception:
                        p = 0
                    found.append({
                        'question': m.get('question', '')[:85],
                        'yes_prob': p,
                        'end_date': m.get('endDate', '')[:10],
                        'volume': m.get('volume', 0),
                    })
    except Exception:
        pass
    # Deduplicate by question
    seen = set()
    unique = []
    for m in found:
        if m['question'] not in seen and m['yes_prob'] > 0.01:
            seen.add(m['question'])
            unique.append(m)
    return unique

with st.spinner("Polymarket 데이터 로딩..."):
    poly_markets = get_polymarket_economic()

# Categorize
FED_KW  = ['fed', 'rate cut', 'rate hike', 'fomc', 'interest rate', 'federal reserve', 'powell', 'emergency cut']
ECON_KW = ['recession', 'gdp', 'unemployment', 'inflation', 'tariff', 'trade war', 'cpi', 'dollar', 'treasury']
MKTCRYPTO_KW = ['s&p', 'nasdaq', 'stock market', 'bitcoin', 'crypto', 'gold', 'oil']

def categorize(q: str):
    ql = q.lower()
    if any(k in ql for k in FED_KW):  return "🏦 연준 정책"
    if any(k in ql for k in ECON_KW): return "📉 거시 경제"
    return "📈 시장/크립토"

for m in poly_markets:
    m['category'] = categorize(m['question'])

if poly_markets:
    cats = ["🏦 연준 정책", "📉 거시 경제", "📈 시장/크립토"]
    tab_fed, tab_econ, tab_mkt = st.tabs(cats)
    tab_map = {"🏦 연준 정책": tab_fed, "📉 거시 경제": tab_econ, "📈 시장/크립토": tab_mkt}

    for cat, tab in tab_map.items():
        with tab:
            cat_mkts = [m for m in poly_markets if m['category'] == cat]
            if not cat_mkts:
                st.info("해당 카테고리 마켓 없음")
                continue
            # Sort by yes_prob proximity to 50% (most uncertain first)
            cat_mkts.sort(key=lambda x: abs(x['yes_prob'] - 0.5))
            for m in cat_mkts[:12]:
                prob = m['yes_prob']
                bar_color = ("#27AE60" if prob > 0.6 else
                             "#E74C3C" if prob < 0.4 else "#F39C12")
                st.markdown(f"""
                <div style='margin:6px 0;padding:8px 12px;background:#F8F9FA;border-radius:6px;
                            border-left:4px solid {bar_color}'>
                <div style='font-size:0.85em;color:#444;margin-bottom:4px'>
                  {m['question']}
                  <span style='float:right;color:#888;font-size:0.8em'>마감: {m['end_date']}</span>
                </div>
                <div style='display:flex;align-items:center;gap:8px'>
                  <div style='background:#E8E8E8;border-radius:4px;height:10px;flex:1;overflow:hidden'>
                    <div style='background:{bar_color};height:100%;width:{prob*100:.0f}%;border-radius:4px'></div>
                  </div>
                  <b style='color:{bar_color};font-size:0.95em;min-width:48px;text-align:right'>
                    {prob:.1%}
                  </b>
                </div>
                </div>
                """, unsafe_allow_html=True)
else:
    st.warning("Polymarket 데이터를 가져오지 못했습니다.")

st.markdown("---")

# ─── 뉴스 & SNS 감성 분석 ───────────────────
st.subheader("📰 뉴스 & 시장 감성 분석")
st.caption("Yahoo Finance 뉴스 기반 키워드 감성 분석 (실시간)")

# Simple keyword-based sentiment scoring
BULL_KW  = ['rally', 'surge', 'gain', 'rise', 'higher', 'bull', 'growth', 'positive',
            'strong', 'recovery', 'rebound', 'record', 'beat', 'better', 'exceed',
            'optimis', 'boost', 'win', 'profit', 'soar', '상승', '반등', '호재', '강세']
BEAR_KW  = ['fall', 'drop', 'decline', 'crash', 'plunge', 'bear', 'loss', 'recession',
            'fear', 'concern', 'warn', 'risk', 'weak', 'miss', 'disappoint', 'cut',
            'tariff', 'war', 'collapse', 'sell', 'slump', '하락', '급락', '악재', '약세']

def score_sentiment(text: str) -> tuple[int, str]:
    """Returns (score -1..+1 scaled, label)"""
    t = text.lower()
    bull = sum(1 for k in BULL_KW if k in t)
    bear = sum(1 for k in BEAR_KW if k in t)
    net = bull - bear
    if net > 1:   return net, "🟢 강세"
    elif net < -1: return net, "🔴 약세"
    else:          return net, "⚪ 중립"

@st.cache_data(ttl=300)
def get_market_news() -> list[dict]:
    items = []
    try:
        for sym in ['^GSPC', '^VIX', 'SPY', 'QQQ']:
            ticker = yf.Ticker(sym)
            for n in (ticker.news or []):
                c = n.get('content', {})
                title = c.get('title', '')
                summary = c.get('summary', '')
                pub = c.get('pubDate', '')[:10]
                provider = c.get('provider', {}).get('displayName', 'Unknown')
                if title:
                    score, label = score_sentiment(title + ' ' + summary)
                    items.append({
                        'title': title,
                        'summary': summary[:120],
                        'pub': pub,
                        'provider': provider,
                        'score': score,
                        'sentiment': label,
                    })
    except Exception:
        pass
    # Deduplicate by title
    seen = set()
    unique = []
    for it in items:
        if it['title'] not in seen:
            seen.add(it['title'])
            unique.append(it)
    return sorted(unique, key=lambda x: x['pub'], reverse=True)[:20]

news_items = get_market_news()

if news_items:
    # Sentiment summary bar
    bull_cnt  = sum(1 for n in news_items if n['score'] > 1)
    bear_cnt  = sum(1 for n in news_items if n['score'] < -1)
    neut_cnt  = len(news_items) - bull_cnt - bear_cnt
    total_cnt = len(news_items)

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("📰 뉴스 수집", f"{total_cnt}건")
    sc2.metric("🟢 강세", f"{bull_cnt}건", f"{bull_cnt/total_cnt*100:.0f}%")
    sc3.metric("🔴 약세", f"{bear_cnt}건", f"{bear_cnt/total_cnt*100:.0f}%")
    sc4.metric("⚪ 중립", f"{neut_cnt}건", f"{neut_cnt/total_cnt*100:.0f}%")

    # Sentiment distribution bar chart
    fig_sent = go.Figure()
    fig_sent.add_trace(go.Bar(
        x=["강세(Bull)", "중립(Neutral)", "약세(Bear)"],
        y=[bull_cnt, neut_cnt, bear_cnt],
        marker_color=["#27AE60", "#95A5A6", "#E74C3C"],
        text=[bull_cnt, neut_cnt, bear_cnt],
        textposition="outside",
    ))
    fig_sent.update_layout(
        height=220, showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis=ax_style(), yaxis=ax_style(),
        **light_layout()
    )
    st.plotly_chart(fig_sent, use_container_width=True)

    st.markdown("**최신 뉴스 피드**")
    sent_filter = st.radio("감성 필터", ["전체", "🟢 강세", "🔴 약세", "⚪ 중립"],
                           horizontal=True)
    filtered_news = news_items
    if sent_filter != "전체":
        filtered_news = [n for n in news_items if n['sentiment'] == sent_filter]

    for n in filtered_news[:10]:
        label = n['sentiment']
        bar_color = ("#27AE60" if "강세" in label else
                     "#E74C3C" if "약세" in label else "#95A5A6")
        st.markdown(f"""
        <div style='margin:4px 0;padding:8px 12px;background:#F8F9FA;border-radius:6px;
                    border-left:4px solid {bar_color}'>
          <div style='display:flex;justify-content:space-between;align-items:flex-start'>
            <span style='font-size:0.88em;color:#222;flex:1;margin-right:12px'>
              <b>{n['title'][:85]}</b>
            </span>
            <span style='color:{bar_color};font-size:0.8em;white-space:nowrap'>
              {label}
            </span>
          </div>
          <div style='font-size:0.78em;color:#777;margin-top:3px'>
            {n['provider']} · {n['pub']}
          </div>
          {"<div style='font-size:0.8em;color:#555;margin-top:3px'>" + n['summary'] + "</div>" if n['summary'] else ""}
        </div>
        """, unsafe_allow_html=True)
else:
    st.warning("뉴스를 가져오지 못했습니다.")

st.markdown("---")

# ─── Major Index Charts ──────────────────────
st.subheader("📈 주요 지수 3개월 차트")
index_syms = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "KOSPI": "^KS11"}
chart_cols = st.columns(len(index_syms))
for col, (name, sym) in zip(chart_cols, index_syms.items()):
    with col:
        try:
            df_idx = yf.Ticker(sym).history(period="3mo")
            if not df_idx.empty:
                pct_chg = (df_idx['Close'].iloc[-1] / df_idx['Close'].iloc[0] - 1) * 100
                color = "#27AE60" if pct_chg >= 0 else "#E74C3C"
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_idx.index, y=df_idx['Close'],
                    mode='lines', name=name,
                    line=dict(color=color, width=2),
                    fill='tozeroy', fillcolor=f'rgba({",".join(str(int(int(color[i:i+2],16))) for i in [1,3,5])},0.08)',
                ))
                fig.update_layout(
                    title=f"{name}  {pct_chg:+.1f}%", height=220,
                    margin=dict(t=35, b=5, l=5, r=5), showlegend=False,
                    xaxis={**ax_style(), "showticklabels": False},
                    yaxis=ax_style(),
                    **light_layout()
                )
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.caption(f"{name} 로드 실패")

st.markdown("---")

# ─── Sector Snapshot ─────────────────────────
st.subheader("🏭 US 섹터 스냅샷")
sectors = {
    "Technology": "XLK", "Financials": "XLF", "Healthcare": "XLV",
    "Energy": "XLE", "Industrials": "XLI", "Consumer Disc": "XLY",
    "Utilities": "XLU", "Materials": "XLB", "Real Estate": "XLRE",
}
sector_data = []
for name, sym in sectors.items():
    try:
        df_s = yf.Ticker(sym).history(period="5d")
        if len(df_s) >= 2:
            chg = (float(df_s['Close'].iloc[-1]) / float(df_s['Close'].iloc[-2]) - 1) * 100
            sector_data.append({"섹터": name, "등락률(%)": round(chg, 2)})
    except Exception:
        pass

if sector_data:
    df_sec = pd.DataFrame(sector_data).sort_values("등락률(%)", ascending=False)
    colors = ["#27AE60" if v >= 0 else "#E74C3C" for v in df_sec["등락률(%)"]]
    fig_sec = go.Figure(go.Bar(
        x=df_sec["섹터"], y=df_sec["등락률(%)"],
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in df_sec["등락률(%)"]],
        textposition="outside",
    ))
    fig_sec.update_layout(
        height=320, showlegend=False,
        margin=dict(t=10, b=10), yaxis_title="등락률 (%)",
        xaxis=ax_style(), yaxis=ax_style(),
        **light_layout()
    )
    st.plotly_chart(fig_sec, use_container_width=True)

st.caption("데이터: Yahoo Finance · CNN Fear & Greed · Polymarket · 5~10분 캐시")
