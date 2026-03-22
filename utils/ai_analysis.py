"""
ai_analysis.py
Claude API 기반 종목 분석 리포트 생성
"""
import os
import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def analyze_stock(ticker: str, info: dict, price_change_1y: float = None) -> str:
    """
    종목 정보를 바탕으로 Claude AI 분석 리포트 생성
    Returns: 한국어 마크다운 리포트 문자열
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "API 키가 설정되지 않았습니다."

    # 핵심 지표 추출
    name = info.get("longName") or ticker
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    market_cap = info.get("marketCap", 0)
    pe = info.get("trailingPE", "N/A")
    forward_pe = info.get("forwardPE", "N/A")
    pb = info.get("priceToBook", "N/A")
    roe = info.get("returnOnEquity", "N/A")
    revenue_growth = info.get("revenueGrowth", "N/A")
    earnings_growth = info.get("earningsGrowth", "N/A")
    debt_equity = info.get("debtToEquity", "N/A")
    current_ratio = info.get("currentRatio", "N/A")
    profit_margin = info.get("profitMargins", "N/A")
    dividend_yield = info.get("dividendYield", "N/A")
    target_price = info.get("targetMeanPrice", "N/A")
    current_price = info.get("currentPrice", "N/A")
    summary = info.get("longBusinessSummary", "")[:500]

    def pct(v):
        try:
            return f"{float(v)*100:.1f}%"
        except Exception:
            return str(v)

    def fmt(v, decimals=2):
        try:
            return f"{float(v):.{decimals}f}"
        except Exception:
            return str(v)

    prompt = f"""당신은 해외주식 전문 애널리스트입니다. 아래 데이터를 바탕으로 한국 투자자를 위한 종목 분석 리포트를 작성하세요.

## 종목 정보
- 티커: {ticker}
- 회사명: {name}
- 섹터: {sector} / {industry}
- 시가총액: {market_cap:,} USD (if available)
- 현재가: {current_price} USD
- 애널리스트 목표가: {target_price} USD
- 1년 수익률: {f"{price_change_1y:.1f}%" if price_change_1y else "N/A"}

## 밸류에이션
- PER(12개월): {fmt(pe)}
- 선행 PER: {fmt(forward_pe)}
- PBR: {fmt(pb)}

## 수익성
- ROE: {pct(roe)}
- 순이익률: {pct(profit_margin)}
- 매출성장률: {pct(revenue_growth)}
- 순이익성장률: {pct(earnings_growth)}

## 재무안정성
- 부채비율(D/E): {fmt(debt_equity)}
- 유동비율: {fmt(current_ratio)}
- 배당수익률: {pct(dividend_yield)}

## 사업 요약
{summary}

---
다음 형식으로 분석 리포트를 작성해주세요:

### 투자 의견 (매수/중립/매도 + 한 줄 이유)

### 핵심 강점 (3가지)

### 주요 리스크 (3가지)

### 밸류에이션 분석 (현재 주가 수준 평가)

### 투자 포인트 요약 (2~3문장, 한국 개인투자자 관점)

※ 본 분석은 AI가 생성한 참고 자료이며 투자 결정의 책임은 투자자 본인에게 있습니다."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except anthropic.RateLimitError:
        return "API 사용량 한도 초과. 잠시 후 다시 시도하세요."
    except Exception as e:
        return f"분석 생성 실패: {e}"


def compare_stocks(tickers: list, infos: dict) -> str:
    """복수 종목 비교 분석"""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "API 키가 설정되지 않았습니다."

    rows = []
    for t in tickers:
        info = infos.get(t, {})
        rows.append(
            f"- {t} ({info.get('longName', t)}): "
            f"PER={info.get('trailingPE', 'N/A')}, "
            f"PBR={info.get('priceToBook', 'N/A')}, "
            f"ROE={info.get('returnOnEquity', 'N/A')}, "
            f"매출성장={info.get('revenueGrowth', 'N/A')}, "
            f"시총={info.get('marketCap', 'N/A'):,}"
        )

    prompt = f"""다음 {len(tickers)}개 종목을 한국 투자자 관점에서 비교 분석해주세요.

{chr(10).join(rows)}

### 종목별 한 줄 평가
### 가장 매력적인 종목 추천 및 이유
### 섹터/업종 관점에서의 포지셔닝 비교
### 리스크 비교

※ 본 분석은 AI 참고 자료입니다."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"비교 분석 실패: {e}"
