"""
daily_runner.py
매일 자동 포트폴리오 최적화 실행 & JSON 저장
"""
import os, json, logging
from datetime import datetime, date
import pandas as pd

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_DIR  = os.path.join(BASE_DIR, "data", "daily_analysis")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("daily_runner")


def daily_result_path(d: date = None) -> str:
    d = d or date.today()
    os.makedirs(DAILY_DIR, exist_ok=True)
    return os.path.join(DAILY_DIR, f"{d.isoformat()}.json")


def load_daily(d: date = None) -> dict:
    path = daily_result_path(d)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_daily(result: dict, d: date = None):
    path = daily_result_path(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"일일 분석 저장: {path}")


def list_daily_dates() -> list:
    """저장된 일별 분석 날짜 목록 (최신순)"""
    if not os.path.exists(DAILY_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(DAILY_DIR) if f.endswith(".json")],
        reverse=True
    )
    return [f.replace(".json", "") for f in files]


def run_daily_analysis(tickers: list, model: str = "max_sharpe",
                       period: str = "1y", top_n: int = 8,
                       force: bool = False) -> dict:
    """
    일일 분석 실행.
    오늘 결과가 이미 있으면 스킵 (force=True 로 강제 재실행).
    """
    today = date.today()
    existing = load_daily(today)
    if existing and not force:
        log.info(f"오늘({today}) 분석 결과 이미 존재 — 스킵")
        return existing

    log.info(f"일일 분석 시작: {today} | 모델={model} | 종목={len(tickers)}개")

    from utils.stock_data import get_price_history
    from utils.optimizer import optimize, walkforward_backtest, momentum_score

    # 가격 수집
    price_data = {}
    for t in tickers:
        h = get_price_history(t, period=period)
        if not h.empty:
            price_data[t] = h["Close"]
    prices = pd.DataFrame(price_data).dropna()

    if len(prices.columns) < 2:
        log.error("유효 종목 부족")
        return {}

    # 최적화
    opt = optimize(prices, model=model, apply_momentum_filter=True, top_n=top_n)

    # 백테스트 (6M train / 1M test)
    bt = walkforward_backtest(prices, model=model,
                               train_months=6, test_months=1,
                               apply_momentum=True)

    # 모멘텀 점수
    mom = momentum_score(prices)

    # 직렬화
    result = {
        "date": today.isoformat(),
        "model": model,
        "tickers_universe": list(prices.columns),
        "weights": {k: round(float(v), 4) for k, v in opt["weights"].items()},
        "stats": {k: round(float(v), 4) for k, v in opt["stats"].items()},
        "momentum_scores": {k: round(float(v), 4)
                            for k, v in mom.items()
                            if pd.notna(v)},
        "backtest_metrics": bt["metrics"],
        "timestamp": datetime.now().isoformat(),
    }

    save_daily(result, today)
    log.info(f"일일 분석 완료: {len(opt['weights'])}개 종목 선정")
    return result


# ── 독립 실행용 (cron에서 호출)
if __name__ == "__main__":
    from utils.universe import MOMENTUM_UNIVERSE
    run_daily_analysis(
        tickers=MOMENTUM_UNIVERSE,
        model="max_sharpe",
        top_n=8,
        force=True,
    )
    print("완료")
