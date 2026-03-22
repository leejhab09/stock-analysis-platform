"""
optimizer.py
포트폴리오 최적화 엔진

지원 모델:
  1. Max Sharpe Ratio  (Markowitz MPT)
  2. Minimum Variance
  3. Risk Parity       (Equal Risk Contribution)
  4. Equal Weight      (Baseline)
  5. Momentum Filter   (1개월 유망 종목 선별)

백테스트: Walk-forward (rolling window)
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Literal

RISK_FREE_RATE = 0.05 / 252  # 연 5% → 일간


# ─────────────────────────────────────────────
# 수익률 계산
# ─────────────────────────────────────────────
def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """일간 로그 수익률"""
    return np.log(prices / prices.shift(1)).dropna()


def annualize(ret_series: pd.Series, periods=252):
    mean_r = ret_series.mean() * periods
    std_r  = ret_series.std() * np.sqrt(periods)
    return mean_r, std_r


# ─────────────────────────────────────────────
# 포트폴리오 지표
# ─────────────────────────────────────────────
def portfolio_stats(weights: np.ndarray, mean_ret: np.ndarray,
                    cov: np.ndarray, periods=252):
    w = np.array(weights)
    ret  = np.dot(w, mean_ret) * periods
    vol  = np.sqrt(np.dot(w, np.dot(cov * periods, w)))
    sharpe = (ret - RISK_FREE_RATE * periods) / (vol + 1e-9)
    return ret, vol, sharpe


# ─────────────────────────────────────────────
# 최적화 함수들
# ─────────────────────────────────────────────
def _base_constraints(n: int):
    return [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

def _bounds(n: int, min_w=0.01, max_w=0.40):
    return [(min_w, max_w)] * n


def max_sharpe(mean_ret: np.ndarray, cov: np.ndarray, n: int) -> np.ndarray:
    """Max Sharpe Ratio (Markowitz MPT)"""
    def neg_sharpe(w):
        r, v, s = portfolio_stats(w, mean_ret, cov)
        return -s

    result = minimize(
        neg_sharpe, x0=np.ones(n) / n,
        method="SLSQP",
        bounds=_bounds(n),
        constraints=_base_constraints(n),
        options={"maxiter": 1000, "ftol": 1e-9},
    )
    w = np.array(result.x)
    w = np.clip(w, 0, 1)
    return w / w.sum()


def min_variance(mean_ret: np.ndarray, cov: np.ndarray, n: int) -> np.ndarray:
    """Minimum Variance Portfolio"""
    def port_vol(w):
        return np.sqrt(np.dot(w, np.dot(cov, w)))

    result = minimize(
        port_vol, x0=np.ones(n) / n,
        method="SLSQP",
        bounds=_bounds(n),
        constraints=_base_constraints(n),
        options={"maxiter": 1000},
    )
    w = np.clip(result.x, 0, 1)
    return w / w.sum()


def risk_parity(cov: np.ndarray, n: int) -> np.ndarray:
    """Risk Parity (Equal Risk Contribution)"""
    def risk_contrib_sq(w):
        w = np.array(w)
        sigma = np.sqrt(np.dot(w, np.dot(cov, w)))
        mrc = np.dot(cov, w) / (sigma + 1e-9)
        rc = w * mrc
        target = sigma / n
        return np.sum((rc - target) ** 2)

    result = minimize(
        risk_contrib_sq, x0=np.ones(n) / n,
        method="SLSQP",
        bounds=_bounds(n, min_w=0.01, max_w=0.60),
        constraints=_base_constraints(n),
        options={"maxiter": 2000},
    )
    w = np.clip(result.x, 0, 1)
    return w / w.sum()


def equal_weight(n: int) -> np.ndarray:
    return np.ones(n) / n


# ─────────────────────────────────────────────
# 모멘텀 필터 (1개월 유망 종목 선별)
# ─────────────────────────────────────────────
def momentum_score(prices: pd.DataFrame,
                   months_short=1, months_long=6) -> pd.Series:
    """
    듀얼 모멘텀 점수:
      score = 0.4 * (1M수익률) + 0.3 * (3M수익률) + 0.3 * (6M수익률)
    양수인 종목만 선별 → 나머지는 0 처리
    """
    d1  = int(months_short * 21)
    d3  = int(3 * 21)
    d6  = int(months_long * 21)

    r1 = prices.iloc[-1] / prices.iloc[-min(d1, len(prices))]  - 1
    r3 = prices.iloc[-1] / prices.iloc[-min(d3, len(prices))]  - 1
    r6 = prices.iloc[-1] / prices.iloc[-min(d6, len(prices))]  - 1

    score = 0.4 * r1 + 0.3 * r3 + 0.3 * r6
    return score


def filter_by_momentum(prices: pd.DataFrame, top_n: int = None,
                       min_score: float = 0.0) -> list:
    """모멘텀 양수 + 상위 top_n 종목 반환"""
    score = momentum_score(prices)
    score = score[score > min_score].sort_values(ascending=False)
    if top_n:
        score = score.head(top_n)
    return score.index.tolist(), score


# ─────────────────────────────────────────────
# 포트폴리오 최적화 통합 함수
# ─────────────────────────────────────────────
def optimize(prices: pd.DataFrame,
             model: Literal["max_sharpe", "min_variance", "risk_parity", "equal_weight"],
             apply_momentum_filter: bool = False,
             top_n: int = None) -> dict:
    """
    Returns:
        weights: dict {ticker: weight}
        stats: {return, volatility, sharpe}
        filtered_tickers: list
    """
    tickers = prices.columns.tolist()

    # 모멘텀 필터 적용
    if apply_momentum_filter:
        filtered, mom_scores = filter_by_momentum(prices, top_n=top_n)
        if len(filtered) < 2:
            filtered = tickers  # fallback
        prices = prices[filtered]
        tickers = filtered
    else:
        mom_scores = momentum_score(prices)

    ret = compute_returns(prices)
    mean_ret = ret.mean().values
    cov      = ret.cov().values
    n        = len(tickers)

    if n == 1:
        w = np.array([1.0])
    elif model == "max_sharpe":
        w = max_sharpe(mean_ret, cov, n)
    elif model == "min_variance":
        w = min_variance(mean_ret, cov, n)
    elif model == "risk_parity":
        w = risk_parity(cov, n)
    else:
        w = equal_weight(n)

    r, v, s = portfolio_stats(w, mean_ret, cov)

    return {
        "weights": dict(zip(tickers, w)),
        "stats": {"annual_return": r, "annual_volatility": v, "sharpe": s},
        "momentum_scores": mom_scores,
        "tickers": tickers,
    }


# ─────────────────────────────────────────────
# Walk-Forward 백테스트
# ─────────────────────────────────────────────
def walkforward_backtest(prices: pd.DataFrame,
                         model: str,
                         train_months: int = 6,
                         test_months: int = 1,
                         apply_momentum: bool = False) -> dict:
    """
    Walk-forward 백테스트:
      - train_months 로 최적화 → test_months 보유 → 반복
      - 벤치마크: 동일비중(Equal Weight)
    Returns:
        portfolio_curve: pd.Series  (누적 수익률)
        benchmark_curve: pd.Series
        metrics: dict
        history: list of {date, weights, sharpe}
    """
    train_days = train_months * 21
    test_days  = test_months  * 21
    total      = len(prices)

    portfolio_returns = []
    benchmark_returns = []
    dates = []
    history = []

    start = train_days
    while start + test_days <= total:
        train = prices.iloc[start - train_days : start]
        test  = prices.iloc[start : start + test_days]

        # 최적화
        try:
            res = optimize(train, model=model, apply_momentum_filter=apply_momentum)
            w_dict = res["weights"]
        except Exception:
            tickers = prices.columns.tolist()
            w_dict = {t: 1/len(tickers) for t in tickers}

        # 수익률 계산 (test 기간)
        test_ret = compute_returns(test)

        # 포트폴리오 수익률 (보유 종목만)
        w_arr = np.array([w_dict.get(t, 0.0) for t in test_ret.columns])
        port_r = test_ret.values @ w_arr

        # 벤치마크 (동일비중)
        bench_r = test_ret.mean(axis=1).values

        portfolio_returns.extend(port_r.tolist())
        benchmark_returns.extend(bench_r.tolist())
        dates.extend(test.index[1:].tolist())  # log-return shifts by 1

        history.append({
            "date": test.index[0].date(),
            "weights": w_dict,
            "sharpe": res.get("stats", {}).get("sharpe", 0),
        })

        start += test_days

    # 누적 수익률
    port_series  = pd.Series(portfolio_returns, index=dates)
    bench_series = pd.Series(benchmark_returns, index=dates)

    port_cum  = (1 + port_series).cumprod()
    bench_cum = (1 + bench_series).cumprod()

    # 성과 지표
    def calc_metrics(ret_series, label):
        ann_ret = ret_series.mean() * 252
        ann_vol = ret_series.std() * np.sqrt(252)
        sharpe  = ann_ret / (ann_vol + 1e-9)
        cum     = (1 + ret_series).cumprod()
        drawdown = (cum / cum.cummax() - 1)
        max_dd  = drawdown.min()
        # Sortino
        neg     = ret_series[ret_series < 0]
        downvol = neg.std() * np.sqrt(252)
        sortino = ann_ret / (downvol + 1e-9)
        # Calmar
        calmar  = ann_ret / (abs(max_dd) + 1e-9)
        return {
            f"{label}_연간수익률": f"{ann_ret*100:.2f}%",
            f"{label}_연간변동성": f"{ann_vol*100:.2f}%",
            f"{label}_샤프비율":   f"{sharpe:.2f}",
            f"{label}_최대낙폭":   f"{max_dd*100:.2f}%",
            f"{label}_소르티노":   f"{sortino:.2f}",
            f"{label}_칼마비율":   f"{calmar:.2f}",
        }

    metrics = {}
    metrics.update(calc_metrics(port_series,  "포트폴리오"))
    metrics.update(calc_metrics(bench_series, "벤치마크"))

    return {
        "portfolio_curve": port_cum,
        "benchmark_curve": bench_cum,
        "metrics": metrics,
        "history": history,
        "port_returns": port_series,
        "bench_returns": bench_series,
    }


# ─────────────────────────────────────────────
# 효율적 프론티어 (시각화용)
# ─────────────────────────────────────────────
def efficient_frontier(mean_ret: np.ndarray, cov: np.ndarray,
                       n_points: int = 60) -> pd.DataFrame:
    """효율적 프론티어 포인트 생성 (랜덤 시뮬레이션)"""
    n = len(mean_ret)
    results = []
    for _ in range(max(n_points * 20, 5000)):
        w = np.random.dirichlet(np.ones(n))
        r, v, s = portfolio_stats(w, mean_ret, cov)
        results.append({"return": r, "volatility": v, "sharpe": s})
    return pd.DataFrame(results)
