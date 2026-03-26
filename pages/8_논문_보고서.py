"""
주식 매매 알고리즘 논문 & 투자기관 전략보고서
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io as _io
import xml.etree.ElementTree as _ET
import requests
from collections import Counter as _Counter

# ── 키워드 분류 ──────────────────────────────────────────────
_ALGO_KW_CATS = {
    "매매 전략": [
        "momentum", "mean reversion", "pairs trading", "arbitrage",
        "market making", "trend following", "contrarian", "statistical arbitrage",
        "high frequency trading", "HFT", "algorithmic trading", "quantitative trading",
        "systematic trading", "factor investing", "alpha",
    ],
    "ML/DL 방법론": [
        "LSTM", "GRU", "transformer", "attention mechanism",
        "reinforcement learning", "deep Q-network", "DQN", "PPO",
        "deep learning", "neural network", "convolutional neural network", "CNN",
        "random forest", "gradient boosting", "XGBoost", "LightGBM",
        "support vector machine", "SVM", "recurrent neural network", "RNN",
        "generative adversarial network", "GAN", "graph neural network",
        "large language model", "LLM", "GPT", "BERT", "sentiment analysis",
    ],
    "데이터/신호": [
        "order book", "limit order book", "LOB", "tick data",
        "high frequency data", "intraday", "candlestick", "OHLCV",
        "technical indicator", "moving average", "RSI", "MACD", "Bollinger",
        "alternative data", "news", "NLP", "social media", "Twitter",
        "earnings", "fundamental", "financial statement",
    ],
    "포트폴리오/리스크": [
        "portfolio optimization", "Markowitz", "mean-variance",
        "Sharpe ratio", "Sortino", "drawdown", "volatility",
        "risk management", "VaR", "CVaR", "Kelly criterion",
        "asset allocation", "rebalancing", "diversification",
    ],
    "시장 미세구조": [
        "market microstructure", "price impact", "slippage",
        "bid-ask spread", "market liquidity", "execution",
        "optimal execution", "TWAP", "VWAP", "Almgren", "Chriss",
    ],
}

PRESET_QUERIES = {
    "직접 입력": "",
    "주식 매매 알고리즘 (종합)": "algorithmic trading stock market machine learning",
    "강화학습 트레이딩": "reinforcement learning stock trading portfolio",
    "LSTM/Transformer 주가 예측": "LSTM transformer stock price prediction deep learning",
    "고빈도 트레이딩 (HFT)": "high frequency trading order book market microstructure",
    "모멘텀/평균회귀 전략": "momentum mean reversion systematic trading strategy",
    "NLP/감성 분석 투자": "sentiment analysis NLP news stock market prediction",
    "포트폴리오 최적화": "portfolio optimization deep learning reinforcement learning",
    "통계적 차익거래": "statistical arbitrage pairs trading cointegration",
    "대안데이터 활용": "alternative data stock prediction machine learning",
}

INSTITUTION_LIST = [
    "직접 입력",
    "Goldman Sachs", "Morgan Stanley", "JPMorgan", "BlackRock",
    "Bridgewater Associates", "Two Sigma", "Renaissance Technologies",
    "Citadel", "AQR Capital", "D.E. Shaw",
    "Samsung Securities", "Mirae Asset", "KB Securities",
    "NH Investment", "Hana Financial", "Korea Investment",
    "CLSA", "UBS", "Barclays", "Deutsche Bank",
]

REPORT_CATEGORIES = [
    "퀀트 전략", "거시경제/시장전망", "섹터 분석", "포트폴리오 전략",
    "리스크 관리", "ESG/대안투자", "파생상품", "기타",
]

# ── 영구 저장 경로 ───────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_PAPERS_PATH  = os.path.join(_DATA_DIR, "papers.json")
_REPORTS_PATH = os.path.join(_DATA_DIR, "reports.json")


def _load_df(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            return pd.read_json(path, orient="records")
        except Exception:
            pass
    return pd.DataFrame()


def _save_df(df: pd.DataFrame, path: str):
    try:
        df.to_json(path, orient="records", force_ascii=False, indent=2)
    except Exception:
        pass


# ── 유틸 함수 ─────────────────────────────────────────────────
def _safe_get(url, params, timeout=12):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def parse_uploaded_pdf(file) -> dict:
    meta = {
        "title": file.name, "authors": "", "year": "", "journal": "",
        "abstract": "", "doi": "", "pdf_url": "", "oa": False,
        "source": "업로드(유료DB)", "citations": 0, "full_text": "",
    }
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            first = ""
            for pg in pdf.pages[:3]:
                t = pg.extract_text()
                if t:
                    first += t + "\n"
            full = first
            for pg in pdf.pages[3:8]:
                t = pg.extract_text()
                if t:
                    full += t + "\n"
        meta["full_text"] = full[:5000]
        lines = [l.strip() for l in first.split("\n") if l.strip()]
        if lines:
            meta["title"] = lines[0][:150]
        doi_m = re.search(r"10\.\d{4,}/[^\s\"'<>]+", full)
        if doi_m:
            meta["doi"] = doi_m.group(0)
        yr_m = re.search(r"\b(19|20)\d{2}\b", first)
        if yr_m:
            meta["year"] = int(yr_m.group(0))
        abs_m = re.search(
            r"(?i)abstract[:\s]*([\s\S]{80,800}?)(?:\n[A-Z\d]|\n\n|introduction|keyword)",
            first,
        )
        if abs_m:
            meta["abstract"] = abs_m.group(1).strip()[:600]
    except Exception:
        pass
    return meta


def parse_report_pdf(file) -> dict:
    meta = {
        "title": os.path.splitext(file.name)[0],
        "institution": "", "date": "", "category": "기타",
        "summary": "", "key_strategy": "", "tickers": "",
        "full_text": "", "filename": file.name,
    }
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            text = ""
            for pg in pdf.pages[:5]:
                t = pg.extract_text()
                if t:
                    text += t + "\n"
        meta["full_text"] = text[:6000]
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            meta["title"] = lines[0][:160]
        date_m = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December"
            r"|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}[-./]\d{1,2}[-./]\d{1,2})",
            text, re.IGNORECASE,
        )
        if date_m:
            meta["date"] = date_m.group(0)
        if not meta["date"]:
            yr_m = re.search(r"\b(20\d{2})\b", text)
            if yr_m:
                meta["date"] = yr_m.group(0)
        for inst in INSTITUTION_LIST[1:]:
            if inst.lower() in text.lower():
                meta["institution"] = inst
                break
        text_lower = text.lower()
        cat_kws = {
            "퀀트 전략": ["quant", "quantitative", "factor", "systematic", "algorithmic"],
            "거시경제/시장전망": ["macro", "gdp", "inflation", "fed", "interest rate", "market outlook"],
            "포트폴리오 전략": ["portfolio", "asset allocation", "diversification", "rebalancing"],
            "리스크 관리": ["risk management", "var", "drawdown", "hedge", "volatility"],
            "파생상품": ["option", "futures", "derivative", "swap", "warrant"],
            "ESG/대안투자": ["esg", "alternative", "private equity", "real estate", "infrastructure"],
            "섹터 분석": ["sector", "industry", "technology", "financial", "healthcare", "energy"],
        }
        for cat, kws in cat_kws.items():
            if any(kw in text_lower for kw in kws):
                meta["category"] = cat
                break
        summ_m = re.search(
            r"(?i)(?:executive summary|key takeaway|summary|overview)[:\s]*([\s\S]{80,800}?)(?:\n[A-Z\d]|\n\n)",
            text,
        )
        if summ_m:
            meta["summary"] = summ_m.group(1).strip()[:600]
        elif len(lines) > 2:
            meta["summary"] = " ".join(lines[1:5])[:400]
        tickers = re.findall(r"\b([A-Z]{2,5})\b", text)
        ticker_freq = _Counter(tickers)
        _stopwords = {
            "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
            "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW",
            "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WHO", "BOY", "DID",
            "GDP", "FED", "USD", "EUR", "CEO", "CFO", "IPO", "ESG", "ETF", "EPS",
            "YOY", "QOQ", "YTD", "BPS", "NPV", "IRR", "ROE", "ROA", "EV",
        }
        meta["tickers"] = ", ".join(
            t for t, _ in ticker_freq.most_common(10)
            if t not in _stopwords and len(t) >= 2
        )
    except Exception:
        pass
    return meta


# ── API 검색 함수 ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def search_openalex(query, max_results=50, year_from=2015, year_to=2025):
    papers = []
    cursor = "*"
    while len(papers) < max_results:
        data = _safe_get("https://api.openalex.org/works", {
            "search": query,
            "filter": f"publication_year:{year_from}-{year_to}",
            "per-page": min(50, max_results - len(papers)),
            "cursor": cursor,
            "select": "title,authorships,publication_year,primary_location,abstract_inverted_index,doi,open_access,cited_by_count",
        })
        if not data:
            break
        items = data.get("results", [])
        if not items:
            break
        for w in items:
            aii = w.get("abstract_inverted_index") or {}
            if aii:
                pos_word = sorted([
                    (pos, word)
                    for word, positions in aii.items()
                    for pos in positions
                ])
                abstract = " ".join(wd for _, wd in pos_word)[:600]
            else:
                abstract = ""
            loc = w.get("primary_location") or {}
            src = loc.get("source") or {}
            papers.append({
                "title": (w.get("title") or "").strip(),
                "authors": ", ".join(
                    (a.get("author") or {}).get("display_name", "")
                    for a in (w.get("authorships") or [])[:3]
                ),
                "year": w.get("publication_year"),
                "journal": src.get("display_name", ""),
                "abstract": abstract,
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "oa": (w.get("open_access") or {}).get("is_oa", False),
                "pdf_url": (w.get("open_access") or {}).get("oa_url", "") or "",
                "source": "OpenAlex",
                "citations": w.get("cited_by_count", 0),
            })
        cursor = (data.get("meta") or {}).get("next_cursor", "")
        if not cursor or len(items) < 10:
            break
    return papers[:max_results]


@st.cache_data(ttl=3600, show_spinner=False)
def search_semantic_scholar(query, max_results=50, year_from=2015, year_to=2025):
    papers = []
    offset = 0
    fields = "title,authors,year,abstract,externalIds,openAccessPdf,publicationVenue,citationCount"
    while len(papers) < max_results:
        data = _safe_get("https://api.semanticscholar.org/graph/v1/paper/search", {
            "query": query,
            "limit": min(100, max_results),
            "offset": offset,
            "fields": fields,
            "year": f"{year_from}-{year_to}",
        })
        if not data:
            break
        items = data.get("data", [])
        if not items:
            break
        for p in items:
            oa_url = (p.get("openAccessPdf") or {}).get("url", "")
            venue = (p.get("publicationVenue") or {}).get("name", "")
            papers.append({
                "title": (p.get("title") or "").strip(),
                "authors": ", ".join(
                    a.get("name", "") for a in (p.get("authors") or [])[:3]
                ),
                "year": p.get("year"),
                "journal": venue,
                "abstract": (p.get("abstract") or "")[:600],
                "doi": (p.get("externalIds") or {}).get("DOI", ""),
                "oa": bool(oa_url),
                "pdf_url": oa_url,
                "source": "Semantic Scholar",
                "citations": p.get("citationCount", 0) or 0,
            })
        offset += len(items)
        if len(items) < 10:
            break
    return papers[:max_results]


@st.cache_data(ttl=3600, show_spinner=False)
def search_arxiv(query, max_results=30, year_from=2015, year_to=2025):
    papers = []
    try:
        r = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "start": 0, "max_results": max_results,
                "sortBy": "relevance",
            },
            timeout=15,
        )
        root = _ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").replace("\n", " ").strip()
            abstract = (entry.findtext("atom:summary", "", ns) or "").replace("\n", " ").strip()[:600]
            published = entry.findtext("atom:published", "", ns)[:4]
            try:
                yr = int(published)
            except Exception:
                yr = None
            if yr and not (year_from <= yr <= year_to):
                continue
            authors = ", ".join(
                (a.findtext("atom:name", "", ns) or "")
                for a in entry.findall("atom:author", ns)[:3]
            )
            pdf_url = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("title") == "pdf":
                    pdf_url = link_el.get("href", "")
                    break
            doi_el = entry.find("{http://arxiv.org/schemas/atom}doi")
            doi = doi_el.text if doi_el is not None else ""
            arxiv_id_m = re.search(r"arxiv\.org/abs/(.+)", (entry.findtext("atom:id", "", ns) or ""))
            if not doi and arxiv_id_m:
                doi = f"arXiv:{arxiv_id_m.group(1)}"
            papers.append({
                "title": title, "authors": authors, "year": yr,
                "journal": "arXiv", "abstract": abstract,
                "doi": doi, "oa": True, "pdf_url": pdf_url,
                "source": "arXiv", "citations": 0,
            })
    except Exception:
        pass
    return papers


def count_algo_keywords(df: pd.DataFrame) -> pd.DataFrame:
    corpus = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.lower()
    rows = []
    for cat, kws in _ALGO_KW_CATS.items():
        for kw in kws:
            cnt = corpus.str.contains(re.escape(kw.lower())).sum()
            rows.append({"분류": cat, "키워드": kw, "빈도": int(cnt)})
    return pd.DataFrame(rows)


def get_lda_topics(df: pd.DataFrame, n_topics: int = 5):
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import LatentDirichletAllocation
        corpus = (df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()
        corpus = [c for c in corpus if len(c.split()) > 10]
        if len(corpus) < 5:
            return []
        tv = TfidfVectorizer(max_features=400, stop_words="english", ngram_range=(1, 2), min_df=2)
        X = tv.fit_transform(corpus)
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42, max_iter=30)
        lda.fit(X)
        feat = tv.get_feature_names_out()
        return [
            f"토픽 {i+1}: " + " / ".join(feat[j] for j in topic.argsort()[:-8:-1])
            for i, topic in enumerate(lda.components_)
        ]
    except Exception:
        return []


# ── 세션 초기화 ───────────────────────────────────────────────
if "papers_df" not in st.session_state:
    st.session_state["papers_df"] = _load_df(_PAPERS_PATH)
if "reports_df" not in st.session_state:
    st.session_state["reports_df"] = _load_df(_REPORTS_PATH)

# ════════════════════════════════════════════════════════════
# 최상위 탭
# ════════════════════════════════════════════════════════════
st.markdown("## 📚 논문 & 전략보고서")
main_tab_papers, main_tab_reports, main_tab_refs = st.tabs([
    "📚 학술 논문 수집", "🏦 투자기관 전략보고서", "🔗 참조 사이트"
])

# ════════════════════════════════════════════════════════════
# 탭 1: 학술 논문 수집
# ════════════════════════════════════════════════════════════
with main_tab_papers:
    st.markdown("#### 📚 주식 매매 알고리즘 학술 논문")
    st.caption("오픈 액세스 자동 수집 (OpenAlex · Semantic Scholar · arXiv) + 유료 DB PDF 업로드")

    col_search, col_upload = st.columns([3, 2])

    with col_search:
        st.markdown("##### 🌐 오픈 액세스 자동 수집")
        st.caption("OpenAlex · Semantic Scholar · arXiv — API Key 불필요, 무료")

        preset = st.selectbox("검색어 프리셋", list(PRESET_QUERIES.keys()), key="p8_preset")
        query_input = st.text_input(
            "검색어 (영문 권장)",
            value=PRESET_QUERIES[preset],
            placeholder="예: reinforcement learning stock trading",
            key="p8_query",
        )

        c_yr1, c_yr2, c_max = st.columns(3)
        with c_yr1:
            year_from = st.number_input("시작 연도", value=2015, step=1, format="%d", key="p8_yr1")
        with c_yr2:
            year_to = st.number_input("종료 연도", value=2025, step=1, format="%d", key="p8_yr2")
        with c_max:
            max_per_src = st.number_input("소스당 최대", value=30, step=10, min_value=5, max_value=100, key="p8_max")

        src_cols = st.columns(3)
        use_openalex = src_cols[0].checkbox("OpenAlex", value=True, key="p8_oa")
        use_ss       = src_cols[1].checkbox("Semantic Scholar", value=True, key="p8_ss")
        use_arxiv    = src_cols[2].checkbox("arXiv", value=True, key="p8_ax")

        if st.button("🔍 논문 자동 수집", type="primary", use_container_width=True, key="p8_search"):
            if not query_input.strip():
                st.warning("검색어를 입력하세요.")
            else:
                collected = []
                total_steps = sum([use_openalex, use_ss, use_arxiv])
                step = 0
                prog = st.progress(0, text="수집 중...")
                if use_openalex:
                    prog.progress(int(step / total_steps * 100), text="OpenAlex 검색 중...")
                    collected.extend(search_openalex(query_input, max_per_src, year_from, year_to))
                    step += 1
                if use_ss:
                    prog.progress(int(step / total_steps * 100), text="Semantic Scholar 검색 중...")
                    collected.extend(search_semantic_scholar(query_input, max_per_src, year_from, year_to))
                    step += 1
                if use_arxiv:
                    prog.progress(int(step / total_steps * 100), text="arXiv 검색 중...")
                    collected.extend(search_arxiv(query_input, max_per_src, year_from, year_to))
                    step += 1
                prog.progress(100, text="완료!")
                if collected:
                    new_df = pd.DataFrame(collected)
                    new_df = new_df[new_df["title"].str.strip().ne("")]
                    new_df["pdf_missing"] = (
                        new_df["oa"].fillna(False) &
                        new_df["pdf_url"].fillna("").str.strip().eq("")
                    )
                    existing = st.session_state["papers_df"]
                    if len(existing) > 0:
                        combined = pd.concat([existing, new_df], ignore_index=True)
                        combined = combined.drop_duplicates(subset=["title"], keep="first").reset_index(drop=True)
                    else:
                        combined = new_df
                    st.session_state["papers_df"] = combined
                    _save_df(combined, _PAPERS_PATH)
                    st.success(f"✅ {len(new_df)}건 수집 → 총 {len(combined)}건 누적")
                else:
                    st.warning("검색 결과 없음.")

    with col_upload:
        st.markdown("##### 📎 유료 DB 논문 PDF 업로드")
        st.caption("ScienceDirect · Web of Science · SSRN 등 직접 다운로드한 PDF")
        uploaded_files = st.file_uploader("PDF 파일 선택 (복수 가능)", type=["pdf"], accept_multiple_files=True, key="p8_pdf_uploader")
        if uploaded_files:
            if st.button("📥 업로드된 PDF 추가", use_container_width=True, key="p8_add_pdf"):
                added = 0
                for f in uploaded_files:
                    meta = parse_uploaded_pdf(f)
                    existing = st.session_state["papers_df"]
                    if len(existing) > 0 and meta["title"] in existing["title"].values:
                        continue
                    new_row = pd.DataFrame([meta])
                    st.session_state["papers_df"] = pd.concat([existing, new_row], ignore_index=True) if len(existing) > 0 else new_row
                    added += 1
                _save_df(st.session_state["papers_df"], _PAPERS_PATH)
                st.success(f"✅ {added}개 PDF 추가 완료")

        if len(st.session_state["papers_df"]) > 0:
            st.markdown("---")
            if st.button("🗑️ 전체 초기화", use_container_width=True, key="p8_reset"):
                st.session_state["papers_df"] = pd.DataFrame()
                _save_df(pd.DataFrame(), _PAPERS_PATH)
                st.rerun()

    # ── KPI + 서브탭 ─────────────────────────────────────────
    df_all = st.session_state["papers_df"]

    if len(df_all) == 0:
        st.info("위에서 검색어를 입력하고 **논문 자동 수집** 버튼을 누르거나, PDF를 업로드하여 시작하세요.")
    else:
        st.divider()
        n_total = len(df_all)
        n_oa    = int(df_all["oa"].sum()) if "oa" in df_all.columns else 0
        n_paid  = int((df_all["source"] == "업로드(유료DB)").sum()) if "source" in df_all.columns else 0
        yr_col  = pd.to_numeric(df_all["year"], errors="coerce").dropna()
        yr_min  = int(yr_col.min()) if len(yr_col) > 0 else "-"
        yr_max  = int(yr_col.max()) if len(yr_col) > 0 else "-"
        avg_cit = df_all["citations"].mean() if "citations" in df_all.columns else 0

        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        kc1.metric("총 논문 수", n_total)
        kc2.metric("오픈 액세스", n_oa)
        kc3.metric("업로드(유료DB)", n_paid)
        kc4.metric("연도 범위", f"{yr_min}~{yr_max}")
        kc5.metric("평균 피인용수", f"{avg_cit:.1f}")

        _pdf_url_col = df_all.get("pdf_url", pd.Series("", index=df_all.index)).fillna("")
        _no_pdf_cnt = int((_pdf_url_col.str.strip() == "").sum())
        _no_pdf_label = "📋 논문 목록" if _no_pdf_cnt == 0 else f"📋 논문 목록  🔴{_no_pdf_cnt}건 미확보"

        tab_list, tab_trend, tab_kw, tab_topic, tab_strategy = st.tabs([
            _no_pdf_label, "📅 연도·저널 트렌드", "🔑 키워드 분석", "🧠 주제 클러스터", "📌 전략 분류",
        ])

        with tab_list:
            df_disp = df_all.copy()
            pdf_url_s = df_disp.get("pdf_url", pd.Series("", index=df_disp.index)).fillna("")
            df_disp["PDF확보"] = pdf_url_s.str.strip().ne("").map({True: "✅ 확보", False: "🔴 미확보"})

            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                src_opts = df_disp["source"].unique().tolist() if "source" in df_disp.columns else []
                src_filter = st.multiselect("소스 필터", src_opts, default=src_opts, key="p8_src_f")
            with fc2:
                kw_filter = st.text_input("제목/초록 키워드 필터", placeholder="예: LSTM, reinforcement, momentum", key="p8_kw_f")
            with fc3:
                pdf_filter = st.selectbox("PDF 상태", ["전체", "🔴 미확보만", "✅ 확보만"], key="p8_pdf_f")

            df_view = df_disp.copy()
            if src_filter and "source" in df_view.columns:
                df_view = df_view[df_view["source"].isin(src_filter)]
            if kw_filter:
                mask = (
                    df_view["title"].fillna("").str.contains(kw_filter, case=False) |
                    df_view["abstract"].fillna("").str.contains(kw_filter, case=False)
                )
                df_view = df_view[mask]
            if pdf_filter == "🔴 미확보만":
                df_view = df_view[df_view["PDF확보"] == "🔴 미확보"]
            elif pdf_filter == "✅ 확보만":
                df_view = df_view[df_view["PDF확보"] == "✅ 확보"]
            if "citations" in df_view.columns:
                df_view = df_view.sort_values("citations", ascending=False)

            ms1, ms2, ms3 = st.columns(3)
            ms1.metric("표시 논문", len(df_view))
            ms2.metric("✅ PDF 확보", (df_view["PDF확보"] == "✅ 확보").sum())
            ms3.metric("🔴 PDF 미확보", (df_view["PDF확보"] == "🔴 미확보").sum())

            show_cols = [c for c in ["PDF확보","title","authors","year","journal","citations","source","doi"] if c in df_view.columns]
            st.dataframe(
                df_view[show_cols].rename(columns={
                    "PDF확보":"PDF","title":"제목","authors":"저자","year":"연도",
                    "journal":"저널","citations":"피인용","source":"출처","doi":"DOI/링크",
                }),
                use_container_width=True, height=440,
                column_config={"PDF": st.column_config.TextColumn("PDF", width="small")},
            )

            if len(df_view) > 0:
                st.markdown("#### 초록 보기")
                sel_t = st.selectbox("논문 선택", df_view["title"].fillna("(제목없음)").tolist(), key="p8_abs_sel")
                sel_row = df_view[df_view["title"] == sel_t].iloc[0]
                st.markdown(f"**{sel_row.get('title','')}**  &nbsp; {sel_row.get('PDF확보','')}")
                st.caption(f"{sel_row.get('authors','')} | {sel_row.get('year','')} | {sel_row.get('journal','')} | {sel_row.get('doi','')}")
                st.text_area("Abstract", sel_row.get("abstract",""), height=180, disabled=True, label_visibility="collapsed")

            st.divider()
            dl1, dl2 = st.columns(2)
            with dl1:
                csv_buf = _io.BytesIO()
                df_view[show_cols].to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button("⬇️ 현재 목록 CSV", csv_buf.getvalue(), file_name="stock_algo_papers.csv", mime="text/csv")
            with dl2:
                df_missing = df_disp[df_disp["PDF확보"] == "🔴 미확보"]
                if len(df_missing) > 0:
                    miss_cols = [c for c in ["title","authors","year","journal","doi","source"] if c in df_missing.columns]
                    miss_buf = _io.BytesIO()
                    df_missing[miss_cols].to_csv(miss_buf, index=False, encoding="utf-8-sig")
                    st.download_button(f"🔴 미확보 논문 목록 CSV ({len(df_missing)}건)", miss_buf.getvalue(), file_name="need_download.csv", mime="text/csv", type="primary")
                else:
                    st.success("모든 논문 PDF 확보 완료!")

        with tab_trend:
            df_tr = df_all.copy()
            df_tr["year"] = pd.to_numeric(df_tr["year"], errors="coerce")
            df_tr = df_tr.dropna(subset=["year"])
            df_tr["year"] = df_tr["year"].astype(int)

            tc1, tc2 = st.columns(2)
            with tc1:
                yr_cnt = df_tr.groupby(["year","source"]).size().reset_index(name="count")
                fig_yr = px.bar(yr_cnt, x="year", y="count", color="source", title="연도별 논문 수 (소스별)",
                                labels={"year":"연도","count":"논문 수","source":"출처"},
                                color_discrete_sequence=px.colors.qualitative.Set2)
                fig_yr.update_layout(height=360, margin=dict(t=40,b=20))
                st.plotly_chart(fig_yr, use_container_width=True)
            with tc2:
                yr_total = df_tr.groupby("year").size().reset_index(name="count").sort_values("year")
                yr_total["누적"] = yr_total["count"].cumsum()
                fig_cum = px.line(yr_total, x="year", y="누적", markers=True, title="누적 논문 수 트렌드",
                                  labels={"year":"연도","누적":"누적 논문 수"}, color_discrete_sequence=["#1a4a8a"])
                fig_cum.add_bar(x=yr_total["year"], y=yr_total["count"], name="연간", marker_color="#a8c5e5", opacity=0.5)
                fig_cum.update_layout(height=360, margin=dict(t=40,b=20))
                st.plotly_chart(fig_cum, use_container_width=True)

            tc3, tc4 = st.columns(2)
            with tc3:
                jrn = df_tr["journal"].fillna("Unknown")
                jrn = jrn[jrn.str.strip().ne("") & jrn.ne("Unknown")]
                if len(jrn) > 0:
                    top_j = jrn.value_counts().head(15).reset_index()
                    top_j.columns = ["journal","count"]
                    fig_j = px.bar(top_j, x="count", y="journal", orientation="h", title="저널/학회별 논문 수 (Top 15)",
                                   labels={"journal":"","count":"논문 수"}, color="count", color_continuous_scale="Blues")
                    fig_j.update_layout(height=420, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                    st.plotly_chart(fig_j, use_container_width=True)
            with tc4:
                if "citations" in df_tr.columns:
                    df_cit = df_tr[df_tr["citations"] > 0].copy()
                    if len(df_cit) > 0:
                        top_cit = df_cit.nlargest(15,"citations")[["title","year","citations"]]
                        top_cit["title_short"] = top_cit["title"].str[:50] + "..."
                        fig_cit = px.bar(top_cit, x="citations", y="title_short", orientation="h", title="피인용수 상위 15편",
                                         labels={"citations":"피인용수","title_short":""}, color="citations", color_continuous_scale="Greens")
                        fig_cit.update_layout(height=420, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                        st.plotly_chart(fig_cit, use_container_width=True)

        with tab_kw:
            kw_df = count_algo_keywords(df_all)
            kw_df = kw_df[kw_df["빈도"] > 0].sort_values("빈도", ascending=False)
            if len(kw_df) == 0:
                st.info("수집된 논문에서 키워드가 감지되지 않았습니다.")
            else:
                kk1, kk2 = st.columns(2)
                with kk1:
                    fig_kw = px.bar(kw_df.head(25), x="빈도", y="키워드", orientation="h", color="분류",
                                    title="매매 알고리즘 키워드 빈도 (Top 25)",
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_kw.update_layout(height=560, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                    st.plotly_chart(fig_kw, use_container_width=True)
                with kk2:
                    cat_sum = kw_df.groupby("분류")["빈도"].sum().reset_index()
                    fig_cat = px.pie(cat_sum, names="분류", values="빈도", title="카테고리별 키워드 비중",
                                     color_discrete_sequence=px.colors.qualitative.Set2)
                    fig_cat.update_layout(height=360, margin=dict(t=40,b=10))
                    st.plotly_chart(fig_cat, use_container_width=True)
                    df_yr_ml = df_all.copy()
                    df_yr_ml["year"] = pd.to_numeric(df_yr_ml["year"], errors="coerce")
                    df_yr_ml = df_yr_ml.dropna(subset=["year"])
                    df_yr_ml["year"] = df_yr_ml["year"].astype(int)
                    corpus_ml = (df_yr_ml["title"].fillna("") + " " + df_yr_ml["abstract"].fillna("")).str.lower()
                    ml_kws = ["deep learning", "reinforcement learning", "lstm", "transformer"]
                    for kw in ml_kws:
                        df_yr_ml[kw] = corpus_ml.str.contains(re.escape(kw)).astype(int)
                    ml_trend = df_yr_ml.groupby("year")[ml_kws].sum().reset_index()
                    if len(ml_trend) > 1:
                        fig_ml = px.line(ml_trend.melt(id_vars="year", var_name="키워드", value_name="논문수"),
                                         x="year", y="논문수", color="키워드", title="ML/DL 핵심 키워드 연도별 추이",
                                         markers=True, color_discrete_sequence=px.colors.qualitative.Bold)
                        fig_ml.update_layout(height=300, margin=dict(t=40,b=20))
                        st.plotly_chart(fig_ml, use_container_width=True)
                st.dataframe(kw_df.reset_index(drop=True), use_container_width=True, height=300)

        with tab_topic:
            st.markdown("#### 🧠 LDA 주제 클러스터링")
            n_topics = st.slider("토픽 수", min_value=3, max_value=10, value=5, key="p8_n_topics")
            if st.button("🔄 토픽 분석 실행", key="p8_run_lda"):
                with st.spinner("LDA 분석 중..."):
                    topics = get_lda_topics(df_all, n_topics)
                if topics:
                    for t in topics:
                        st.markdown(f"- {t}")
                else:
                    st.warning("논문 수가 부족하거나 scikit-learn이 설치되지 않았습니다.")
            st.divider()
            st.markdown("#### 📊 상위 저자")
            if "authors" in df_all.columns:
                all_authors = []
                for row in df_all["authors"].fillna(""):
                    for a in row.split(","):
                        a = a.strip()
                        if a:
                            all_authors.append(a)
                if all_authors:
                    auth_cnt = pd.Series(_Counter(all_authors)).sort_values(ascending=False).head(20)
                    fig_auth = px.bar(x=auth_cnt.values, y=auth_cnt.index, orientation="h",
                                      title="논문 수 상위 저자 (Top 20)", labels={"x":"논문 수","y":""},
                                      color=auth_cnt.values, color_continuous_scale="Purples")
                    fig_auth.update_layout(height=480, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                    st.plotly_chart(fig_auth, use_container_width=True)

        with tab_strategy:
            st.markdown("#### 📌 매매 전략 카테고리별 논문 분류")
            st.caption("제목 + 초록 키워드 매칭으로 자동 분류 (중복 포함 가능)")
            corpus = (df_all["title"].fillna("") + " " + df_all["abstract"].fillna("")).str.lower()
            strategy_map = {
                "강화학습 트레이딩": ["reinforcement learning","deep q-network","dqn","ppo","actor-critic","rl agent"],
                "딥러닝 예측": ["lstm","gru","transformer","cnn","deep learning","neural network","price prediction"],
                "모멘텀/추세추종": ["momentum","trend following","moving average","breakout","dual momentum"],
                "평균회귀/페어트레이딩": ["mean reversion","pairs trading","cointegration","statistical arbitrage","spread trading"],
                "NLP/감성분석": ["sentiment","news","nlp","text mining","social media","twitter","earnings call"],
                "고빈도/시장미세구조": ["high frequency","hft","order book","limit order","market microstructure","execution"],
                "포트폴리오 최적화": ["portfolio optimization","asset allocation","mean-variance","markowitz","sharpe","diversification"],
                "팩터/퀀트 전략": ["factor","value investing","growth","quality","low volatility","factor model","fama"],
            }
            strat_counts = {}
            strat_papers = {}
            for strat, kws in strategy_map.items():
                mask = pd.Series([False] * len(df_all), index=df_all.index)
                for kw in kws:
                    mask = mask | corpus.str.contains(re.escape(kw))
                matched = df_all[mask]
                strat_counts[strat] = len(matched)
                strat_papers[strat] = matched
            strat_df = pd.DataFrame(list(strat_counts.items()), columns=["전략","논문 수"]).sort_values("논문 수", ascending=False)
            sc1, sc2 = st.columns(2)
            with sc1:
                fig_strat = px.bar(strat_df, x="논문 수", y="전략", orientation="h", title="전략 카테고리별 논문 수",
                                   color="논문 수", color_continuous_scale="Tealrose")
                fig_strat.update_layout(height=400, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig_strat, use_container_width=True)
            with sc2:
                fig_strat_pie = px.pie(strat_df[strat_df["논문 수"] > 0], names="전략", values="논문 수",
                                       title="전략 분포 비율", color_discrete_sequence=px.colors.qualitative.Pastel2)
                fig_strat_pie.update_layout(height=400, margin=dict(t=40,b=10))
                st.plotly_chart(fig_strat_pie, use_container_width=True)
            available_strats = [s for s in strategy_map.keys() if strat_counts[s] > 0]
            if available_strats:
                sel_strat = st.selectbox("전략 선택", available_strats, key="p8_strat_sel")
                if sel_strat:
                    df_strat = strat_papers[sel_strat]
                    if "citations" in df_strat.columns:
                        df_strat = df_strat.sort_values("citations", ascending=False)
                    show_cols2 = [c for c in ["title","authors","year","journal","citations","doi"] if c in df_strat.columns]
                    st.dataframe(df_strat[show_cols2].rename(columns={"title":"제목","authors":"저자","year":"연도","journal":"저널","citations":"피인용","doi":"DOI"}),
                                 use_container_width=True, height=360)
                    strat_buf = _io.BytesIO()
                    df_strat[show_cols2].to_csv(strat_buf, index=False, encoding="utf-8-sig")
                    st.download_button(f"⬇️ {sel_strat} 논문 CSV", strat_buf.getvalue(), file_name=f"stock_{sel_strat}.csv", mime="text/csv")
            else:
                st.info("전략 분류에 해당하는 논문이 없습니다. 먼저 논문을 수집해주세요.")


# ════════════════════════════════════════════════════════════
# 탭 2: 투자기관 전략보고서
# ════════════════════════════════════════════════════════════
with main_tab_reports:
    st.markdown("#### 🏦 투자기관 전략보고서")
    st.caption("Goldman Sachs · Morgan Stanley · JPMorgan 등 투자기관 리서치/전략보고서 PDF 업로드 및 관리")

    rp_col1, rp_col2 = st.columns([3, 2])

    with rp_col1:
        st.markdown("##### 📎 보고서 PDF 업로드")
        st.caption("PDF 자동 파싱 — 투자기관명, 날짜, 카테고리, 핵심 요약 자동 추출")
        report_files = st.file_uploader("보고서 PDF 선택 (복수 가능)", type=["pdf"], accept_multiple_files=True, key="p8_report_uploader")
        if report_files:
            rp_inst_sel = st.selectbox("투자기관 (자동감지 또는 직접 선택)", INSTITUTION_LIST, key="p8_rp_inst_sel")
            rp_inst_manual = ""
            if rp_inst_sel == "직접 입력":
                rp_inst_manual = st.text_input("기관명 직접 입력", key="p8_rp_inst_manual")
            rp_cat_sel = st.selectbox("카테고리 (자동분류 또는 직접 선택)", ["자동분류"] + REPORT_CATEGORIES, key="p8_rp_cat")
            rp_memo = st.text_area("메모 (선택)", placeholder="이 보고서의 핵심 인사이트나 메모를 입력하세요.", height=80, key="p8_rp_memo")
            if st.button("📥 보고서 추가", type="primary", use_container_width=True, key="p8_add_reports"):
                added = 0
                with st.spinner("PDF 파싱 중..."):
                    for f in report_files:
                        meta = parse_report_pdf(f)
                        if rp_inst_sel != "직접 입력":
                            meta["institution"] = rp_inst_sel
                        elif rp_inst_manual:
                            meta["institution"] = rp_inst_manual
                        if rp_cat_sel != "자동분류":
                            meta["category"] = rp_cat_sel
                        meta["memo"] = rp_memo
                        existing = st.session_state["reports_df"]
                        if len(existing) > 0 and meta["filename"] in existing["filename"].values:
                            continue
                        new_row = pd.DataFrame([meta])
                        st.session_state["reports_df"] = pd.concat([existing, new_row], ignore_index=True) if len(existing) > 0 else new_row
                        added += 1
                _save_df(st.session_state["reports_df"], _REPORTS_PATH)
                st.success(f"✅ {added}개 보고서 추가 완료")

    with rp_col2:
        st.markdown("##### 📋 업로드 현황")
        df_rep = st.session_state["reports_df"]
        n_rep = len(df_rep)
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("총 보고서", n_rep)
        if n_rep > 0 and "institution" in df_rep.columns:
            rc2.metric("기관 수", df_rep["institution"].nunique())
            rc3.metric("카테고리 수", df_rep["category"].nunique())
        else:
            rc2.metric("기관 수", 0)
            rc3.metric("카테고리 수", 0)
        if n_rep > 0:
            st.markdown("---")
            if st.button("🗑️ 보고서 전체 초기화", use_container_width=True, key="p8_reset_reports"):
                st.session_state["reports_df"] = pd.DataFrame()
                _save_df(pd.DataFrame(), _REPORTS_PATH)
                st.rerun()

    df_rep = st.session_state["reports_df"]
    if n_rep == 0:
        st.info("위에서 투자기관 전략보고서 PDF를 업로드하여 시작하세요.")
    else:
        st.divider()
        rep_tab_list, rep_tab_chart, rep_tab_detail = st.tabs(["📋 보고서 목록", "📊 기관·카테고리 분석", "🔍 상세 보기"])

        with rep_tab_list:
            rf1, rf2, rf3 = st.columns([2, 2, 1])
            with rf1:
                inst_opts = df_rep["institution"].unique().tolist() if "institution" in df_rep.columns else []
                inst_filter = st.multiselect("기관 필터", inst_opts, default=inst_opts, key="p8_rep_inst_f")
            with rf2:
                rep_kw = st.text_input("제목/요약 키워드 검색", placeholder="예: momentum, AI, rate hike", key="p8_rep_kw_f")
            with rf3:
                cat_opts = ["전체"] + (df_rep["category"].unique().tolist() if "category" in df_rep.columns else [])
                cat_filter = st.selectbox("카테고리", cat_opts, key="p8_rep_cat_f")
            df_rep_view = df_rep.copy()
            if inst_filter and "institution" in df_rep_view.columns:
                df_rep_view = df_rep_view[df_rep_view["institution"].isin(inst_filter)]
            if rep_kw:
                mask = (df_rep_view["title"].fillna("").str.contains(rep_kw, case=False) |
                        df_rep_view["summary"].fillna("").str.contains(rep_kw, case=False))
                df_rep_view = df_rep_view[mask]
            if cat_filter != "전체" and "category" in df_rep_view.columns:
                df_rep_view = df_rep_view[df_rep_view["category"] == cat_filter]
            show_rep_cols = [c for c in ["institution","title","date","category","tickers","memo"] if c in df_rep_view.columns]
            st.dataframe(df_rep_view[show_rep_cols].rename(columns={"institution":"기관","title":"제목","date":"날짜","category":"카테고리","tickers":"주요 티커","memo":"메모"}),
                         use_container_width=True, height=440)
            st.divider()
            if len(df_rep_view) > 0:
                rep_csv_buf = _io.BytesIO()
                df_rep_view[show_rep_cols].to_csv(rep_csv_buf, index=False, encoding="utf-8-sig")
                st.download_button("⬇️ 보고서 목록 CSV", rep_csv_buf.getvalue(), file_name="investment_reports.csv", mime="text/csv")

        with rep_tab_chart:
            ch1, ch2 = st.columns(2)
            with ch1:
                if "institution" in df_rep.columns:
                    inst_cnt = df_rep["institution"].value_counts().reset_index()
                    inst_cnt.columns = ["기관","보고서 수"]
                    inst_cnt = inst_cnt[inst_cnt["기관"].str.strip().ne("")]
                    if len(inst_cnt) > 0:
                        fig_inst = px.bar(inst_cnt, x="보고서 수", y="기관", orientation="h", title="기관별 보고서 수",
                                          color="보고서 수", color_continuous_scale="Blues")
                        fig_inst.update_layout(height=400, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                        st.plotly_chart(fig_inst, use_container_width=True)
            with ch2:
                if "category" in df_rep.columns:
                    cat_cnt = df_rep["category"].value_counts().reset_index()
                    cat_cnt.columns = ["카테고리","보고서 수"]
                    if len(cat_cnt) > 0:
                        fig_cat2 = px.pie(cat_cnt, names="카테고리", values="보고서 수", title="카테고리 분포",
                                          color_discrete_sequence=px.colors.qualitative.Set3)
                        fig_cat2.update_layout(height=400, margin=dict(t=40,b=10))
                        st.plotly_chart(fig_cat2, use_container_width=True)
            if "tickers" in df_rep.columns:
                all_tickers = []
                for row in df_rep["tickers"].fillna(""):
                    for t in row.split(","):
                        t = t.strip()
                        if t:
                            all_tickers.append(t)
                if all_tickers:
                    ticker_cnt = pd.Series(_Counter(all_tickers)).sort_values(ascending=False).head(20)
                    fig_tick = px.bar(x=ticker_cnt.values, y=ticker_cnt.index, orientation="h",
                                      title="보고서에 자주 등장하는 티커/종목 (Top 20)", labels={"x":"등장 빈도","y":""},
                                      color=ticker_cnt.values, color_continuous_scale="Oranges")
                    fig_tick.update_layout(height=460, margin=dict(t=40,b=20), yaxis={"categoryorder":"total ascending"})
                    st.plotly_chart(fig_tick, use_container_width=True)

        with rep_tab_detail:
            if len(df_rep) > 0:
                sel_rep = st.selectbox("보고서 선택", df_rep["title"].fillna("(제목없음)").tolist(), key="p8_rep_detail_sel")
                rep_row = df_rep[df_rep["title"] == sel_rep].iloc[0]
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("기관", rep_row.get("institution","-") or "-")
                d2.metric("날짜", rep_row.get("date","-") or "-")
                d3.metric("카테고리", rep_row.get("category","-") or "-")
                d4.metric("파일명", rep_row.get("filename","-") or "-")
                st.markdown("**요약**")
                st.text_area("요약", rep_row.get("summary",""), height=150, disabled=True, label_visibility="collapsed")
                if rep_row.get("tickers"):
                    st.markdown(f"**주요 티커:** `{rep_row.get('tickers','')}`")
                if rep_row.get("memo"):
                    st.markdown(f"**메모:** {rep_row.get('memo','')}")
                with st.expander("원문 텍스트 (추출본)", expanded=False):
                    st.text(rep_row.get("full_text","")[:3000])


# ════════════════════════════════════════════════════════════
# 탭 3: 참조 사이트
# ════════════════════════════════════════════════════════════
with main_tab_refs:
    st.markdown("#### 🔗 주식 매매 알고리즘 참조 사이트")
    st.caption("논문·보고서·데이터·코드 수집에 활용할 수 있는 주요 사이트 모음")

    st.markdown("##### 📄 학술 논문 데이터베이스")
    academic_sites = [
        ("arXiv (q-fin)", "https://arxiv.org/list/q-fin/recent", "퀀트 금융 최신 논문 (무료 전문)"),
        ("SSRN", "https://www.ssrn.com/index.cfm/en/", "금융·경제 워킹페이퍼 (무료 다수)"),
        ("Semantic Scholar", "https://www.semanticscholar.org/", "AI 기반 논문 검색, 무료 API"),
        ("OpenAlex", "https://openalex.org/", "오픈 학술 메타데이터, 무료 API"),
        ("Google Scholar", "https://scholar.google.com/", "종합 학술 검색"),
        ("Papers With Code", "https://paperswithcode.com/task/stock-market-prediction", "논문 + 구현 코드 함께 제공"),
        ("Journal of Financial Economics", "https://www.jfinec.com/", "금융 경제학 최상위 저널"),
        ("Quantitative Finance", "https://www.tandfonline.com/journals/rquf20", "퀀트 파이낸스 전문 저널"),
    ]
    ac_cols = st.columns(2)
    for i, (name, url, desc) in enumerate(academic_sites):
        with ac_cols[i % 2]:
            st.markdown(f"**[{name}]({url})**  \n{desc}")

    st.divider()
    st.markdown("##### 🏦 투자기관 공개 리서치·보고서")
    bank_sites = [
        ("Goldman Sachs Insights", "https://www.goldmansachs.com/insights/", "GS 공개 매크로·전략 리포트"),
        ("JPMorgan Research", "https://www.jpmorgan.com/insights/research", "JPM 리서치 허브"),
        ("Morgan Stanley Ideas", "https://www.morganstanley.com/ideas", "MS 공개 투자 아이디어"),
        ("BlackRock Investment Institute", "https://www.blackrock.com/us/individual/insights/blackrock-investment-institute", "BII 매크로·자산배분 보고서"),
        ("AQR Insights", "https://www.aqr.com/Insights", "AQR 팩터·퀀트 전략 논문·보고서"),
        ("Bridgewater Research", "https://www.bridgewater.com/research-and-insights/", "브리지워터 공개 리서치"),
        ("Deutsche Bank Research", "https://www.dbresearch.com/", "DB 공개 리서치 (일부 무료)"),
        ("CLSA Research", "https://www.clsa.com/ideas/", "아시아 중심 리서치"),
    ]
    bk_cols = st.columns(2)
    for i, (name, url, desc) in enumerate(bank_sites):
        with bk_cols[i % 2]:
            st.markdown(f"**[{name}]({url})**  \n{desc}")

    st.divider()
    st.markdown("##### 🇰🇷 국내 기관 리서치")
    kr_sites = [
        ("삼성증권 리서치", "https://www.samsungpop.com/mobile/researchCenter.do", "국내 리서치 센터"),
        ("미래에셋증권 리서치", "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1520", "리서치·투자전략"),
        ("KB증권 리서치", "https://www.kbsec.com/go.able?no=researchMain", "KB 투자전략"),
        ("한국투자증권 리서치", "https://www.truefriend.com/main/research/strategy.jsp", "주식·파생 전략"),
        ("자본시장연구원 (KCMI)", "https://www.kcmi.re.kr/report/report_list.asp", "자본시장 정책·학술 보고서"),
        ("한국은행 BOK경제연구", "https://www.bok.or.kr/portal/bbs/P0002353/list.do", "금융·경제 연구 보고서"),
    ]
    kr_cols = st.columns(2)
    for i, (name, url, desc) in enumerate(kr_sites):
        with kr_cols[i % 2]:
            st.markdown(f"**[{name}]({url})**  \n{desc}")

    st.divider()
    st.markdown("##### 💾 데이터 & 코드 리소스")
    data_sites = [
        ("QuantConnect (LEAN)", "https://www.quantconnect.com/", "클라우드 백테스트 플랫폼, 무료 데이터"),
        ("Backtrader", "https://www.backtrader.com/", "Python 백테스트 라이브러리"),
        ("zipline-reloaded", "https://github.com/stefan-jansen/zipline-reloaded", "Zipline 백테스트 (Python)"),
        ("vectorbt", "https://vectorbt.dev/", "초고속 벡터화 백테스트"),
        ("Kaggle Finance Datasets", "https://www.kaggle.com/datasets?search=stock", "주식 관련 공개 데이터셋"),
        ("Yahoo Finance API (yfinance)", "https://github.com/ranaroussi/yfinance", "주가·재무 무료 데이터"),
        ("FRED (Federal Reserve)", "https://fred.stlouisfed.org/", "미국 거시경제 데이터"),
        ("KRX 정보데이터시스템", "http://data.krx.co.kr/", "국내 주식·파생 공식 데이터"),
        ("OpenDartReader", "https://github.com/FinanceData/OpenDartReader", "DART 공시 데이터 Python 패키지"),
        ("FinanceData.KR", "https://financedata.github.io/", "국내 금융 데이터 Python 튜토리얼"),
    ]
    dt_cols = st.columns(2)
    for i, (name, url, desc) in enumerate(data_sites):
        with dt_cols[i % 2]:
            st.markdown(f"**[{name}]({url})**  \n{desc}")

    st.divider()
    st.markdown("##### 💬 커뮤니티 & 블로그")
    community_sites = [
        ("QuantLib", "https://www.quantlib.org/", "오픈소스 퀀트 라이브러리"),
        ("Quant Stack Exchange", "https://quant.stackexchange.com/", "퀀트 Q&A 커뮤니티"),
        ("Wilmott Forum", "https://forum.wilmott.com/", "퀀트 파이낸스 전문 포럼"),
        ("Investopedia", "https://www.investopedia.com/", "금융 개념·전략 사전"),
        ("Towards Data Science (Finance)", "https://towardsdatascience.com/tagged/finance", "ML+금융 실전 아티클"),
        ("퀀트투자 커뮤니티 (QALAB)", "https://www.quantlab.co.kr/", "국내 퀀트 투자 커뮤니티"),
    ]
    cm_cols = st.columns(2)
    for i, (name, url, desc) in enumerate(community_sites):
        with cm_cols[i % 2]:
            st.markdown(f"**[{name}]({url})**  \n{desc}")
