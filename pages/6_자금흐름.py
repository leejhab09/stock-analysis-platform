"""
pages/6_자금흐름.py — 투자자별 자금흐름 (기관/개인/외국인)
섹터별 Sankey 다이어그램 + 시계열 차트 + 히트맵 + 상세 데이터
"""

import time
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from bs4 import BeautifulSoup
from io import StringIO
from datetime import date, timedelta

st.set_page_config(page_title="자금흐름", page_icon="💰", layout="wide")

# ─── Constants ──────────────────────────────────────────────────────────────

SECTOR_STOCKS = {
    "반도체":      ["005930", "000660"],
    "자동차":      ["005380", "000270"],
    "바이오":      ["068270", "207940"],
    "배터리":      ["373220", "006400", "051910"],
    "금융":        ["105560", "055550", "032830"],
    "방산/조선":   ["012450", "329180", "042660"],
    "IT/플랫폼":   ["035420", "035720"],
    "통신":        ["017670", "030200"],
    "에너지/화학": ["096770", "034020"],
    "유통/소비":   ["028260", "012330"],
}

TICKER_NAME_KR = {
    "005930": "삼성전자",      "000660": "SK하이닉스",
    "005380": "현대차",        "000270": "기아",
    "068270": "셀트리온",      "207940": "삼성바이오",
    "373220": "LG에너지솔루션","006400": "삼성SDI",      "051910": "LG화학",
    "105560": "KB금융",        "055550": "신한지주",     "032830": "삼성생명",
    "012450": "한화에어로스페이스", "329180": "HD현대중공업", "042660": "한화오션",
    "035420": "NAVER",         "035720": "카카오",
    "017670": "SK텔레콤",      "030200": "KT",
    "096770": "SK이노베이션",  "034020": "두산에너빌리티",
    "028260": "삼성물산",      "012330": "현대모비스",
}

# Build reverse map: ticker → sector
TICKER_TO_SECTOR = {}
for sector, tickers in SECTOR_STOCKS.items():
    for t in tickers:
        TICKER_TO_SECTOR[t] = sector

INVESTOR_COLORS = {
    "기관":   "#2196F3",
    "외국인": "#4CAF50",
    "개인":   "#FF9800",
}
INVESTOR_LINK_COLORS = {
    "기관":   "rgba(33,150,243,0.4)",
    "외국인": "rgba(76,175,80,0.4)",
    "개인":   "rgba(255,152,0,0.4)",
}
SECTOR_COLOR = "#9C27B0"

EOKWON = 1_0000_0000  # 1억원 = 100,000,000원

# ─── Data Fetching ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_investor_data(ticker: str) -> pd.DataFrame:
    """Scrape investor net buy data from Naver Finance for one ticker."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content.decode("cp949", errors="ignore"), "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 4:
            return pd.DataFrame()
        df = pd.read_html(StringIO(str(tables[3])))[0]
        # Flatten multi-level columns
        df.columns = [
            "날짜", "종가", "전일비", "등락률", "거래량",
            "기관_순매매", "외국인_순매매", "외국인_보유주수", "외국인_보유율"
        ]
        df = df[df["날짜"].notna() & (df["날짜"] != "날짜")].copy()
        df["날짜"] = pd.to_datetime(df["날짜"].astype(str).str.strip(), format="%Y.%m.%d", errors="coerce")
        df = df.dropna(subset=["날짜"])
        df["기관_순매매"]  = pd.to_numeric(df["기관_순매매"],  errors="coerce").fillna(0)
        df["외국인_순매매"] = pd.to_numeric(df["외국인_순매매"], errors="coerce").fillna(0)
        df["개인_순매매"]  = -(df["기관_순매매"] + df["외국인_순매매"])
        df["종가"] = pd.to_numeric(df["종가"].astype(str).str.replace(",", ""), errors="coerce")
        df["ticker"] = ticker
        df["섹터"]  = TICKER_TO_SECTOR.get(ticker, "기타")
        df["종목명"] = TICKER_NAME_KR.get(ticker, ticker)
        # Convert shares → KRW value
        df["기관_순매수액"]  = df["기관_순매매"]  * df["종가"]
        df["외국인_순매수액"] = df["외국인_순매매"] * df["종가"]
        df["개인_순매수액"]  = df["개인_순매매"]  * df["종가"]
        return df.sort_values("날짜", ascending=False).head(30)
    except Exception as e:
        st.warning(f"[{ticker}] 데이터 로드 실패: {e}")
        return pd.DataFrame()


def load_all_data() -> pd.DataFrame:
    """Fetch all tickers sequentially and concatenate."""
    all_tickers = [t for tickers in SECTOR_STOCKS.values() for t in tickers]
    frames = []
    with st.spinner(f"데이터 로드 중... {len(all_tickers)}개 종목"):
        for i, ticker in enumerate(all_tickers):
            df = fetch_investor_data(ticker)
            if not df.empty:
                frames.append(df)
            if i < len(all_tickers) - 1:
                time.sleep(0.3)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ─── Helper: aggregate sector flows ─────────────────────────────────────────

def aggregate_sector_flows(df: pd.DataFrame) -> dict:
    """
    For each (investor, sector), sum net purchase in 억원.
    Returns dict: {investor: {sector: value_억}}
    """
    result = {inv: {} for inv in ["기관", "외국인", "개인"]}
    col_map = {"기관": "기관_순매수액", "외국인": "외국인_순매수액", "개인": "개인_순매수액"}
    for sector in SECTOR_STOCKS:
        sector_df = df[df["섹터"] == sector]
        for inv, col in col_map.items():
            if col in sector_df.columns:
                total = sector_df[col].sum()
                result[inv][sector] = round(total / EOKWON, 1)
            else:
                result[inv][sector] = 0.0
    return result


def aggregate_daily_sector(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by (날짜, 섹터) and sum net purchase columns.
    Returns DataFrame with columns: 날짜, 섹터, 기관(억원), 외국인(억원), 개인(억원), 합계(억원)
    """
    grouped = df.groupby(["날짜", "섹터"], as_index=False)[
        ["기관_순매수액", "외국인_순매수액", "개인_순매수액"]
    ].sum()
    grouped["기관(억원)"]  = (grouped["기관_순매수액"]  / EOKWON).round(1)
    grouped["외국인(억원)"] = (grouped["외국인_순매수액"] / EOKWON).round(1)
    grouped["개인(억원)"]  = (grouped["개인_순매수액"]  / EOKWON).round(1)
    grouped["합계(억원)"]  = (grouped["기관(억원)"] + grouped["외국인(억원)"] + grouped["개인(억원)"]).round(1)
    return grouped.sort_values(["날짜", "합계(억원)"], ascending=[False, False])


# ─── Chart builders ──────────────────────────────────────────────────────────

def build_sankey(sector_flows: dict, start_date, end_date) -> go.Figure:
    node_labels = ["기관", "외국인", "개인"] + list(SECTOR_STOCKS.keys())
    node_colors = (
        [INVESTOR_COLORS["기관"], INVESTOR_COLORS["외국인"], INVESTOR_COLORS["개인"]]
        + [SECTOR_COLOR] * len(SECTOR_STOCKS)
    )
    investor_idx = {"기관": 0, "외국인": 1, "개인": 2}
    sector_idx   = {s: i + 3 for i, s in enumerate(SECTOR_STOCKS.keys())}

    sources, targets, values, link_colors = [], [], [], []

    for investor in ["기관", "외국인", "개인"]:
        for sector, value_억 in sector_flows[investor].items():
            if abs(value_억) < 0.1:
                continue
            if value_억 > 0:  # net buyer: investor → sector
                sources.append(investor_idx[investor])
                targets.append(sector_idx[sector])
                values.append(value_억)
                link_colors.append(INVESTOR_LINK_COLORS[investor])
            else:             # net seller: sector → investor
                sources.append(sector_idx[sector])
                targets.append(investor_idx[investor])
                values.append(-value_억)
                link_colors.append(INVESTOR_LINK_COLORS[investor])

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=node_labels,
            color=node_colors,
            pad=20,
            thickness=20,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
        ),
    ))
    fig.update_layout(
        title_text="투자자별 섹터 자금흐름",
        height=620,
        font_size=13,
        paper_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def build_stacked_bar(daily_df: pd.DataFrame, investor_col: str, investor_label: str, color: str) -> go.Figure:
    """Stacked bar chart per sector for one investor type."""
    sectors = list(SECTOR_STOCKS.keys())
    fig = go.Figure()
    palette = [
        "#E91E63", "#9C27B0", "#3F51B5", "#03A9F4", "#009688",
        "#8BC34A", "#FF9800", "#795548", "#607D8B", "#F44336",
    ]
    for i, sector in enumerate(sectors):
        s_df = daily_df[daily_df["섹터"] == sector].sort_values("날짜")
        fig.add_trace(go.Bar(
            x=s_df["날짜"],
            y=s_df[investor_col],
            name=sector,
            marker_color=palette[i % len(palette)],
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig.update_layout(
        barmode="stack",
        title=f"{investor_label} 섹터별 순매수 (억원)",
        xaxis_title="날짜",
        yaxis_title="순매수 (억원)",
        legend_title="섹터",
        height=450,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFAFA",
        font=dict(size=12),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def build_total_line(daily_df: pd.DataFrame, investor_col: str, investor_label: str, color: str) -> go.Figure:
    """Line chart of daily total (all sectors summed) for one investor."""
    total = daily_df.groupby("날짜")[investor_col].sum().reset_index()
    total = total.sort_values("날짜")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=total["날짜"],
        y=total[investor_col],
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=5),
        name=investor_label,
        fill="tozeroy",
        fillcolor=color.replace(")", ",0.15)").replace("rgb(", "rgba(") if "rgb" in color else color + "26",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig.update_layout(
        title=f"{investor_label} 전체 순매수 합계 (억원)",
        xaxis_title="날짜",
        yaxis_title="순매수 (억원)",
        height=300,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFAFA",
        font=dict(size=12),
        showlegend=False,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def build_heatmap(daily_df: pd.DataFrame, investor_col: str, investor_label: str) -> go.Figure:
    """Heatmap: sectors × dates, z = net purchase 억원."""
    pivot = daily_df.pivot_table(
        index="섹터", columns="날짜", values=investor_col, aggfunc="sum"
    ).fillna(0)
    # Sort sectors by SECTOR_STOCKS order
    ordered_sectors = [s for s in SECTOR_STOCKS.keys() if s in pivot.index]
    pivot = pivot.loc[ordered_sectors]

    # Format column labels as strings
    col_labels = [str(c)[:10] for c in pivot.columns]
    z_vals = pivot.values.round(1)

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=col_labels,
        y=list(pivot.index),
        colorscale="RdYlGn",
        zmid=0,
        text=[[f"{v:.1f}" for v in row] for row in z_vals],
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title="억원"),
    ))
    fig.update_layout(
        title=f"{investor_label} 섹터별 순매수 히트맵 (억원)",
        xaxis_title="날짜",
        yaxis_title="섹터",
        height=450,
        paper_bgcolor="#FFFFFF",
        font=dict(size=12),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


# ─── Page Layout ─────────────────────────────────────────────────────────────

st.title("💰 투자자별 자금흐름")
st.markdown("기관·개인·외국인의 섹터별 순매수 흐름을 분석합니다.")
st.markdown("---")

# ─── Controls ────────────────────────────────────────────────────────────────

col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 1])

today = date.today()
default_end   = today
default_start = today - timedelta(days=28)  # ~20 business days

with col_ctrl1:
    date_range = st.date_input(
        "기준 기간",
        value=(default_start, default_end),
        format="YYYY-MM-DD",
    )

with col_ctrl2:
    st.markdown("<br>", unsafe_allow_html=True)
    load_btn = st.button("📥 데이터 로드", type="primary", use_container_width=True)

# Resolve date range
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range[0], date_range[1]
else:
    start_date, end_date = default_start, default_end

# Session state keys
if "flow_data" not in st.session_state:
    st.session_state["flow_data"] = None
if "flow_loaded_date" not in st.session_state:
    st.session_state["flow_loaded_date"] = None

if load_btn:
    raw = load_all_data()
    st.session_state["flow_data"] = raw
    st.session_state["flow_loaded_date"] = (start_date, end_date)

# Show badge reflecting the currently-selected date range (updates live with widget)
if st.session_state["flow_data"] is not None:
    with col_ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<span style="background:#e3f2fd;color:#1565c0;padding:4px 10px;'
            f'border-radius:8px;font-size:0.85rem;">기준일: {start_date} ~ {end_date}</span>',
            unsafe_allow_html=True,
        )

# ─── Main content (only if data loaded) ─────────────────────────────────────

raw_df = st.session_state.get("flow_data")

if raw_df is None or raw_df.empty:
    st.info("위의 '📥 데이터 로드' 버튼을 클릭하여 데이터를 불러오세요.")
    st.stop()

# Filter by selected date range
filtered_df = raw_df[
    (raw_df["날짜"].dt.date >= start_date) &
    (raw_df["날짜"].dt.date <= end_date)
].copy()

if filtered_df.empty:
    st.warning("선택한 기간에 해당하는 데이터가 없습니다. 기간을 조정하거나 데이터를 다시 로드해주세요.")
    st.stop()

# ─── Summary Metrics ─────────────────────────────────────────────────────────

st.markdown("### 📊 상단 요약")
total_inst   = round(filtered_df["기관_순매수액"].sum()  / EOKWON, 1)
total_fore   = round(filtered_df["외국인_순매수액"].sum() / EOKWON, 1)
total_indiv  = round(filtered_df["개인_순매수액"].sum()  / EOKWON, 1)

m1, m2, m3 = st.columns(3)

def fmt_eok(v: float) -> str:
    return f"{v:+,.1f} 억원"

with m1:
    st.metric(
        label="🏢 기관 총순매수",
        value=fmt_eok(total_inst),
        delta=f"{'매수' if total_inst >= 0 else '매도'}",
        delta_color="normal" if total_inst >= 0 else "inverse",
    )
with m2:
    st.metric(
        label="🌐 외국인 총순매수",
        value=fmt_eok(total_fore),
        delta=f"{'매수' if total_fore >= 0 else '매도'}",
        delta_color="normal" if total_fore >= 0 else "inverse",
    )
with m3:
    st.metric(
        label="👤 개인 총순매수",
        value=fmt_eok(total_indiv),
        delta=f"{'매수' if total_indiv >= 0 else '매도'}",
        delta_color="normal" if total_indiv >= 0 else "inverse",
    )

st.markdown("---")

# ─── Precompute aggregated data ──────────────────────────────────────────────

sector_flows = aggregate_sector_flows(filtered_df)
daily_sector = aggregate_daily_sector(filtered_df)

# ─── Tabs ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "🔀 Sankey 자금흐름",
    "📈 시계열 변화",
    "🗺️ 섹터 히트맵",
    "📋 상세 데이터",
])

# ── Tab 1: Sankey ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("투자자 → 섹터 자금흐름 (Sankey)")
    sankey_fig = build_sankey(sector_flows, start_date, end_date)
    st.plotly_chart(sankey_fig, use_container_width=True)
    st.caption(f"기준: {start_date} ~ {end_date} | 단위: 억원 | 화살표 방향: 순매수(투자자→섹터), 순매도(섹터→투자자)")

    # Sector summary table under Sankey
    st.markdown("#### 섹터별 투자자 순매수 요약 (억원)")
    rows = []
    for sector in SECTOR_STOCKS:
        rows.append({
            "섹터": sector,
            "기관(억원)":   sector_flows["기관"].get(sector, 0),
            "외국인(억원)": sector_flows["외국인"].get(sector, 0),
            "개인(억원)":   sector_flows["개인"].get(sector, 0),
        })
    summary_df = pd.DataFrame(rows)
    summary_df["합계(억원)"] = (
        summary_df["기관(억원)"] + summary_df["외국인(억원)"] + summary_df["개인(억원)"]
    ).round(1)
    summary_df = summary_df.sort_values("합계(억원)", ascending=False)
    st.dataframe(
        summary_df.style.format({
            "기관(억원)":   "{:+.1f}",
            "외국인(억원)": "{:+.1f}",
            "개인(억원)":   "{:+.1f}",
            "합계(억원)":   "{:+.1f}",
        }).background_gradient(subset=["합계(억원)"], cmap="RdYlGn", vmin=-500, vmax=500),
        use_container_width=True,
        hide_index=True,
    )

# ── Tab 2: Time-series ───────────────────────────────────────────────────────
with tab2:
    st.subheader("투자자별 시계열 순매수 변화")
    sub_tabs = st.tabs(["🏢 기관", "🌐 외국인", "👤 개인"])

    investor_info = [
        ("기관",   "기관(억원)",   INVESTOR_COLORS["기관"]),
        ("외국인", "외국인(억원)", INVESTOR_COLORS["외국인"]),
        ("개인",   "개인(억원)",   INVESTOR_COLORS["개인"]),
    ]

    for sub_tab, (inv_label, inv_col, inv_color) in zip(sub_tabs, investor_info):
        with sub_tab:
            st.markdown(f"#### {inv_label} 섹터별 순매수 (누적 스택 바)")
            bar_fig = build_stacked_bar(daily_sector, inv_col, inv_label, inv_color)
            st.plotly_chart(bar_fig, use_container_width=True)

            st.markdown(f"#### {inv_label} 전체 합계 추이")
            line_fig = build_total_line(daily_sector, inv_col, inv_label, inv_color)
            st.plotly_chart(line_fig, use_container_width=True)

# ── Tab 3: Heatmap ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("섹터별 순매수 히트맵")
    hmap_inv = st.radio(
        "투자자 선택",
        ["기관", "외국인", "개인", "전체합계"],
        horizontal=True,
    )
    col_map = {
        "기관":    "기관(억원)",
        "외국인":  "외국인(억원)",
        "개인":    "개인(억원)",
        "전체합계": "합계(억원)",
    }
    hmap_col = col_map[hmap_inv]
    hmap_fig = build_heatmap(daily_sector, hmap_col, hmap_inv)
    st.plotly_chart(hmap_fig, use_container_width=True)
    st.caption(f"기준: {start_date} ~ {end_date} | 단위: 억원 | 빨강=순매도, 초록=순매수")

# ── Tab 4: Detail Table ──────────────────────────────────────────────────────
with tab4:
    st.subheader("섹터별 일자별 상세 데이터")
    detail_df = daily_sector[["날짜", "섹터", "기관(억원)", "외국인(억원)", "개인(억원)", "합계(억원)"]].copy()
    detail_df["날짜"] = detail_df["날짜"].dt.strftime("%Y-%m-%d")
    detail_df = detail_df.sort_values(["날짜", "합계(억원)"], ascending=[False, False])

    # Search / filter
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        sector_filter = st.multiselect(
            "섹터 필터",
            options=list(SECTOR_STOCKS.keys()),
            default=list(SECTOR_STOCKS.keys()),
        )
    with col_f2:
        investor_filter = st.selectbox(
            "정렬 기준 투자자",
            options=["합계(억원)", "기관(억원)", "외국인(억원)", "개인(억원)"],
        )

    if sector_filter:
        detail_df = detail_df[detail_df["섹터"].isin(sector_filter)]

    detail_df = detail_df.sort_values(["날짜", investor_filter], ascending=[False, False])

    st.dataframe(
        detail_df.style.format({
            "기관(억원)":   "{:+.1f}",
            "외국인(억원)": "{:+.1f}",
            "개인(억원)":   "{:+.1f}",
            "합계(억원)":   "{:+.1f}",
        }).background_gradient(subset=["합계(억원)"], cmap="RdYlGn", vmin=-200, vmax=200),
        use_container_width=True,
        hide_index=True,
        height=500,
    )
    st.caption(f"총 {len(detail_df):,}행 | 기준: {start_date} ~ {end_date}")

    # Download button
    csv_bytes = detail_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ CSV 다운로드",
        data=csv_bytes,
        file_name=f"자금흐름_{start_date}_{end_date}.csv",
        mime="text/csv",
    )
