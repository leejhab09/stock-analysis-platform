"""
ai_analysis.py
Claude API 기반 종목 분석 및 포트폴리오 AI 기능

A. explain_portfolio       — 최적화 비중 AI 해설
B. get_news_sentiment      — 뉴스 감성분석 → 기대수익률 보정용 점수
C. rebalancing_advice      — 일일 리밸런싱 필요 여부 AI 판단
D. interpret_backtest      — 백테스트 결과 AI 해석 + 전략 개선 제안
"""
import os
import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _client():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("API 키가 설정되지 않았습니다.")
    return anthropic.Anthropic(api_key=api_key)


def _call(prompt: str, max_tokens: int = 1200) -> str:
    try:
        msg = _client().messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except anthropic.RateLimitError:
        return "API 사용량 한도 초과. 잠시 후 다시 시도하세요."
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"분석 생성 실패: {e}"


# ──────────────────────────────────────────────────
# A. 포트폴리오 비중 AI 해설
# ──────────────────────────────────────────────────
def explain_portfolio(weights: dict, stats: dict,
                      momentum_scores: dict = None,
                      model_name: str = "Max Sharpe") -> str:
    """
    최적화 결과(비중, 통계)를 바탕으로 AI가 한국어로 해설
    - 왜 이 종목이 높은 비중을 받았는지
    - 포트폴리오 전반적 성격 분석
    - 주의사항
    """
    w_lines = "\n".join([
        f"  - {t}: {v*100:.1f}%" for t, v in
        sorted(weights.items(), key=lambda x: -x[1])
    ])

    mom_lines = ""
    if momentum_scores:
        mom_lines = "\n모멘텀 점수:\n" + "\n".join([
            f"  - {t}: {v*100:.2f}%"
            for t, v in sorted(momentum_scores.items(),
                                key=lambda x: -x[1])[:10]
        ])

    prompt = f"""당신은 퀀트 포트폴리오 전문가입니다.
아래는 {model_name} 알고리즘으로 최적화된 포트폴리오입니다.
한국 개인투자자가 이해할 수 있도록 쉽고 명확하게 해설해주세요.

## 최적화 결과
모델: {model_name}
편입 비중:
{w_lines}

예상 성과 (연간):
  - 기대수익률: {stats.get('annual_return', 0)*100:.2f}%
  - 변동성: {stats.get('annual_volatility', 0)*100:.2f}%
  - 샤프비율: {stats.get('sharpe', 0):.2f}
{mom_lines}

다음 항목을 포함하여 해설해주세요:

### 포트폴리오 성격 요약
(공격적/방어적/균형형 등 전반적 특성)

### 주요 편입 종목 선정 이유
(상위 3~4개 종목 위주로, 왜 높은 비중이 배분됐는지)

### 섹터 분산도 평가
(특정 섹터 집중 여부, 분산 효과)

### 예상 시나리오
(상승장/하락장에서 이 포트폴리오가 어떻게 반응할지)

### 투자자 유의사항
(이 포트폴리오의 약점이나 주의해야 할 점)

※ 본 해설은 AI 참고 자료입니다. 투자 책임은 투자자 본인에게 있습니다."""

    return _call(prompt, max_tokens=1500)


# ──────────────────────────────────────────────────
# B. 뉴스 감성분석 → 기대수익률 보정 점수
# ──────────────────────────────────────────────────
def get_news_sentiment(tickers: list) -> dict:
    """
    각 종목의 최근 뉴스 헤드라인을 수집하여 감성 점수(-1.0 ~ +1.0) 반환
    최적화 시 기대수익률 보정에 사용
    """
    import yfinance as yf
    import json

    news_by_ticker = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            news = tk.news or []
            headlines = [n.get("title", "") for n in news[:5] if n.get("title")]
            news_by_ticker[t] = headlines
        except Exception:
            news_by_ticker[t] = []

    # 뉴스가 전혀 없으면 중립 반환
    has_news = any(v for v in news_by_ticker.values())
    if not has_news:
        return {t: 0.0 for t in tickers}

    news_text = "\n".join([
        f"{t}:\n" + "\n".join([f"  - {h}" for h in headlines]) if headlines
        else f"{t}: (뉴스 없음)"
        for t, headlines in news_by_ticker.items()
    ])

    prompt = f"""아래는 각 주식 종목의 최근 뉴스 헤드라인입니다.
각 종목의 투자 감성을 -1.0(매우 부정)에서 +1.0(매우 긍정) 사이 숫자로 평가해주세요.

뉴스:
{news_text}

반드시 아래 JSON 형식으로만 답하세요. 설명 없이 JSON만 출력:
{{
  "TICKER1": 0.3,
  "TICKER2": -0.1,
  ...
}}"""

    try:
        result = _call(prompt, max_tokens=300)
        # JSON 파싱
        start = result.find("{")
        end   = result.rfind("}") + 1
        if start >= 0 and end > start:
            scores = json.loads(result[start:end])
            # 유효 범위 클리핑
            return {t: max(-1.0, min(1.0, float(scores.get(t, 0.0))))
                    for t in tickers}
    except Exception:
        pass

    return {t: 0.0 for t in tickers}


# ──────────────────────────────────────────────────
# C. 일일 리밸런싱 AI 판단
# ──────────────────────────────────────────────────
def rebalancing_advice(today_weights: dict, prev_weights: dict,
                       today_stats: dict, prev_stats: dict,
                       momentum_scores: dict = None) -> str:
    """
    오늘 vs 이전 포트폴리오를 비교하여 리밸런싱 필요 여부 AI 판단
    """
    all_tickers = list(dict.fromkeys(
        list(today_weights.keys()) + list(prev_weights.keys())
    ))

    changes = []
    for t in all_tickers:
        tw = today_weights.get(t, 0) * 100
        pw = prev_weights.get(t, 0) * 100
        diff = tw - pw
        changes.append(f"  - {t}: {pw:.1f}% → {tw:.1f}% ({diff:+.1f}%p)")

    mom_text = ""
    if momentum_scores:
        top_mom = sorted(momentum_scores.items(), key=lambda x: -x[1])[:5]
        mom_text = "최근 모멘텀 상위 종목:\n" + "\n".join(
            [f"  - {t}: {v*100:.1f}%" for t, v in top_mom]
        )

    prompt = f"""당신은 포트폴리오 리밸런싱 전문가입니다.
일일 포트폴리오 최적화 결과를 분석하고 실제 리밸런싱 필요 여부를 판단해주세요.

## 포트폴리오 변화
{chr(10).join(changes)}

## 성과 지표 변화
- 샤프비율: {prev_stats.get('sharpe', 0):.2f} → {today_stats.get('sharpe', 0):.2f}
- 기대수익률: {prev_stats.get('annual_return', 0)*100:.2f}% → {today_stats.get('annual_return', 0)*100:.2f}%
- 변동성: {prev_stats.get('annual_volatility', 0)*100:.2f}% → {today_stats.get('annual_volatility', 0)*100:.2f}%

{mom_text}

다음 항목으로 판단해주세요:

### 리밸런싱 권고 (즉시/이번 주 내/불필요)
(한 줄 결론 + 이유)

### 주요 변화 분석
(비중이 크게 바뀐 종목 중심으로)

### 거래 우선순위
(매수 강화 / 비중 축소 순서)

### 주의 사항
(거래비용, 세금, 타이밍 관점)

※ AI 참고 자료입니다. 투자 책임은 투자자 본인에게 있습니다."""

    return _call(prompt, max_tokens=1200)


# ──────────────────────────────────────────────────
# D. 백테스트 결과 AI 해석
# ──────────────────────────────────────────────────
def interpret_backtest(metrics: dict, history: list,
                       model_name: str = "Max Sharpe",
                       period: str = "2년") -> str:
    """
    Walk-forward 백테스트 결과를 AI가 해석하고 전략 개선점 제안
    """
    port_ret  = metrics.get("포트폴리오_연간수익률", "N/A")
    port_vol  = metrics.get("포트폴리오_연간변동성", "N/A")
    port_shr  = metrics.get("포트폴리오_샤프비율", "N/A")
    port_mdd  = metrics.get("포트폴리오_최대낙폭", "N/A")
    port_sor  = metrics.get("포트폴리오_소르티노", "N/A")
    port_cal  = metrics.get("포트폴리오_칼마비율", "N/A")

    bench_ret = metrics.get("벤치마크_연간수익률", "N/A")
    bench_shr = metrics.get("벤치마크_샤프비율", "N/A")
    bench_mdd = metrics.get("벤치마크_최대낙폭", "N/A")

    # 리밸런싱 이력 요약
    hist_text = ""
    if history:
        avg_sharpe = sum(h.get("sharpe", 0) for h in history) / len(history)
        hist_text = (f"리밸런싱 횟수: {len(history)}회\n"
                     f"평균 샤프비율(학습기간): {avg_sharpe:.2f}")

    prompt = f"""당신은 퀀트 투자 전략 전문가입니다.
아래 Walk-forward 백테스트 결과를 분석하고 전략 개선점을 제안해주세요.

## 백테스트 개요
- 모델: {model_name}
- 데이터 기간: {period}
- {hist_text}

## 포트폴리오 성과
| 지표 | 포트폴리오 | 벤치마크(동일비중) |
|------|-----------|------------------|
| 연간수익률 | {port_ret} | {bench_ret} |
| 샤프비율 | {port_shr} | {bench_shr} |
| 최대낙폭(MDD) | {port_mdd} | {bench_mdd} |
| 연간변동성 | {port_vol} | N/A |
| 소르티노비율 | {port_sor} | N/A |
| 칼마비율 | {port_cal} | N/A |

다음 항목으로 해석해주세요:

### 전략 성과 종합 평가
(벤치마크 대비 알파 창출 여부, 위험조정수익률 평가)

### 강점
(이 전략이 잘 작동한 부분)

### 약점 및 한계
(MDD, 변동성 등 약점 분석)

### 개선 제안 3가지
(구체적인 파라미터 조정 또는 전략 보완 방법)

### 실전 적용 시 주의사항
(과최적화 위험, 거래비용, 시장 환경 변화 등)

※ AI 참고 자료입니다. 투자 책임은 투자자 본인에게 있습니다."""

    return _call(prompt, max_tokens=1500)


# ──────────────────────────────────────────────────
# 기존 함수 (종목분석, 종목비교) — 유지
# ──────────────────────────────────────────────────
def analyze_stock(ticker: str, info: dict, price_change_1y: float = None) -> str:
    name     = info.get("longName") or ticker
    sector   = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    market_cap     = info.get("marketCap", 0)
    pe             = info.get("trailingPE", "N/A")
    forward_pe     = info.get("forwardPE", "N/A")
    pb             = info.get("priceToBook", "N/A")
    roe            = info.get("returnOnEquity", "N/A")
    revenue_growth = info.get("revenueGrowth", "N/A")
    earnings_growth= info.get("earningsGrowth", "N/A")
    debt_equity    = info.get("debtToEquity", "N/A")
    current_ratio  = info.get("currentRatio", "N/A")
    profit_margin  = info.get("profitMargins", "N/A")
    dividend_yield = info.get("dividendYield", "N/A")
    target_price   = info.get("targetMeanPrice", "N/A")
    current_price  = info.get("currentPrice", "N/A")
    summary        = info.get("longBusinessSummary", "")[:500]

    def pct(v):
        try: return f"{float(v)*100:.1f}%"
        except Exception: return str(v)
    def fmt(v, d=2):
        try: return f"{float(v):.{d}f}"
        except Exception: return str(v)

    prompt = f"""당신은 해외주식 전문 애널리스트입니다. 아래 데이터를 바탕으로 한국 투자자를 위한 종목 분석 리포트를 작성하세요.

## 종목 정보
- 티커: {ticker} / 회사명: {name}
- 섹터: {sector} / {industry}
- 현재가: {current_price} USD  |  목표가: {target_price} USD
- 1년 수익률: {f"{price_change_1y:.1f}%" if price_change_1y else "N/A"}

## 밸류에이션
PER: {fmt(pe)}  |  선행PER: {fmt(forward_pe)}  |  PBR: {fmt(pb)}

## 수익성
ROE: {pct(roe)}  |  순이익률: {pct(profit_margin)}  |  매출성장: {pct(revenue_growth)}  |  EPS성장: {pct(earnings_growth)}

## 재무안정성
D/E: {fmt(debt_equity)}  |  유동비율: {fmt(current_ratio)}  |  배당: {pct(dividend_yield)}

## 사업 요약
{summary}

---
### 투자 의견 (매수/중립/매도 + 한 줄 이유)
### 핵심 강점 (3가지)
### 주요 리스크 (3가지)
### 밸류에이션 분석
### 투자 포인트 요약 (2~3문장)

※ AI 참고 자료. 투자 책임은 투자자 본인에게 있습니다."""

    return _call(prompt, max_tokens=1200)


def compare_stocks(tickers: list, infos: dict) -> str:
    rows = []
    for t in tickers:
        info = infos.get(t, {})
        rows.append(
            f"- {t} ({info.get('longName', t)}): "
            f"PER={info.get('trailingPE','N/A')}, "
            f"PBR={info.get('priceToBook','N/A')}, "
            f"ROE={info.get('returnOnEquity','N/A')}, "
            f"매출성장={info.get('revenueGrowth','N/A')}"
        )
    prompt = f"""다음 {len(tickers)}개 종목을 한국 투자자 관점에서 비교 분석해주세요.

{chr(10).join(rows)}

### 종목별 한 줄 평가
### 가장 매력적인 종목 추천 및 이유
### 섹터/업종 관점 포지셔닝 비교
### 리스크 비교

※ AI 참고 자료입니다."""
    return _call(prompt, max_tokens=1000)
