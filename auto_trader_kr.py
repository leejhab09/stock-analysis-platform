"""
auto_trader_kr.py — 국내 주식 페이퍼 매매 자동 실행 엔진
- 5분마다 조건 체크 (KST 09:00~15:30, 평일)
- 국내 시장 특화 알고리즘 적용
- data/journal/KR_YYYY-MM-DD.json 일지 기록
실행: python3 auto_trader_kr.py
"""
import os, sys, json, logging
from datetime import datetime, date
import numpy as np
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.kr_stock_data import analyze_kr_ticker, get_kospi_change, get_kosdaq_change, suffix

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "data")
JOURNAL_DIR    = os.path.join(DATA_DIR, "journal")
KR_PORT_FILE   = os.path.join(DATA_DIR, "kr_portfolio.json")
KR_TRADES_FILE = os.path.join(DATA_DIR, "kr_paper_trades.json")
KR_STRAT_FILE  = os.path.join(DATA_DIR, "kr_strategy_config.json")
KR_LOG_FILE    = os.path.join(DATA_DIR, "auto_trader_kr.log")
os.makedirs(JOURNAL_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [KR] %(message)s",
    handlers=[
        logging.FileHandler(KR_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("auto_trader_kr")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_kr_market_open() -> bool:
    """KST 09:00~15:30, 평일"""
    kst    = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)
    if now_kst.weekday() >= 5:
        return False
    open_t  = now_kst.replace(hour=9,  minute=0,  second=0, microsecond=0)
    close_t = now_kst.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now_kst <= close_t

def market_status() -> str:
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    return f"KST {now.strftime('%H:%M')} ({'장중' if is_kr_market_open() else '장외'})"

# ── 국내 주식 매수 조건 체크 ─────────────────────────────────
def check_kr_conditions(row: dict, cfg: dict, kospi_chg: float | None) -> tuple[bool, dict]:
    results = {}

    # ① 당일 낙폭 (필수)
    results["당일 낙폭"] = (
        row["change_pct"] <= cfg["drop_threshold"],
        f"{row['change_pct']:+.2f}% (기준 {cfg['drop_threshold']:.1f}%)"
    )

    # ② RSI 과매도
    if cfg.get("use_rsi", True):
        results["RSI 과매도"] = (
            row["rsi"] <= cfg["rsi_threshold"],
            f"RSI={row['rsi']:.1f} (기준 ≤{cfg['rsi_threshold']})"
        )

    # ③ KOSPI/KOSDAQ 대비 초과 낙폭 (종목 고유 원인 가능성)
    if cfg.get("use_relative", True) and kospi_chg is not None:
        excess = row["change_pct"] - kospi_chg
        results["지수 대비 초과 낙폭"] = (
            excess <= cfg["relative_drop"],
            f"종목{row['change_pct']:+.2f}% - 지수{kospi_chg:+.2f}% = {excess:+.2f}% (기준 ≤{cfg['relative_drop']:.1f}%)"
        )

    # ④ 거래량 급등 (관심·수급 확인)
    if cfg.get("use_volume", True):
        results["거래량 급등"] = (
            row["vol_ratio"] >= cfg["vol_ratio_min"],
            f"거래량비율={row['vol_ratio']:.2f}x (기준 ≥{cfg['vol_ratio_min']:.1f}x)"
        )

    # ⑤ 볼린저 밴드 하단 접근 (%B < 0.2)
    if cfg.get("use_bb", True):
        results["볼린저 하단"] = (
            row["bb_pct"] <= cfg["bb_threshold"],
            f"%B={row['bb_pct']:.2f} (기준 ≤{cfg['bb_threshold']:.2f})"
        )

    passed = all(v[0] for v in results.values())
    return passed, results

def update_journal(entry: dict):
    today   = date.today().isoformat()
    jfile   = os.path.join(JOURNAL_DIR, f"KR_{today}.json")
    journal = load_json(jfile, {"date": today, "market": "KR", "scans": [], "trades": [], "summary": {}})
    etype   = entry.pop("_type", "scan")
    journal[etype + "s"].append(entry)
    trades  = journal["trades"]
    journal["summary"] = {
        "total_scans":    len(journal["scans"]),
        "total_trades":   len(trades),
        "total_invested": sum(t["amount_krw"] for t in trades),
        "tickers_traded": list({t["ticker"] for t in trades}),
        "last_updated":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(jfile, journal)

# ── 매도 체크 ─────────────────────────────────────────────────
def check_kr_sells(cfg: dict, price_map: dict):
    """open 포지션 중 익절/손절/기간청산 조건 충족 시 자동 매도 기록"""
    import yfinance as yf
    trades = load_json(KR_TRADES_FILE, [])
    open_trades = [t for t in trades if t.get("status") == "open"]
    if not open_trades:
        return

    tp  = cfg.get("take_profit_pct", 5.0)
    sl  = cfg.get("stop_loss_pct", -5.0)
    mhd = cfg.get("max_hold_days", 20)
    updated = False

    for t in open_trades:
        tk   = suffix(t["ticker"])
        curr = price_map.get(tk)
        if curr is None:
            try:
                hist = yf.Ticker(tk).history(period="2d")
                curr = float(hist["Close"].iloc[-1]) if not hist.empty else None
            except Exception:
                pass
        if curr is None:
            continue

        buy_price = t["price"]
        pnl_pct   = (curr - buy_price) / buy_price * 100

        try:
            buy_dt    = datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S")
            hold_days = (datetime.now() - buy_dt).days
        except Exception:
            hold_days = 0

        reason = None
        if pnl_pct >= tp:
            reason = f"익절 (+{pnl_pct:.2f}% ≥ +{tp}%)"
        elif pnl_pct <= sl:
            reason = f"손절 ({pnl_pct:.2f}% ≤ {sl}%)"
        elif hold_days >= mhd:
            reason = f"기간청산 ({hold_days}일 보유)"

        if reason:
            pnl_krw = round((curr - buy_price) * t["qty"])
            t["status"]     = "closed"
            t["sell_price"] = curr
            t["sell_date"]  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t["pnl_krw"]    = pnl_krw
            t["pnl_pct"]    = round(pnl_pct, 2)
            t["sell_reason"]= reason
            updated = True
            log.info(f"  💰 자동매도: {t['ticker']} {t.get('name','')} {t['qty']}주 "
                     f"@ ₩{curr:,} | PnL ₩{pnl_krw:+,} ({pnl_pct:+.2f}%) | {reason}")
            update_journal({
                "_type":      "trade",
                "action":     "SELL",
                "time":       datetime.now().strftime("%H:%M:%S"),
                "ticker":     t["ticker"],
                "name":       t.get("name", t["ticker"]),
                "price":      curr,
                "qty":        t["qty"],
                "amount_krw": round(curr * t["qty"]),
                "pnl_krw":    pnl_krw,
                "pnl_pct":    round(pnl_pct, 2),
                "hold_days":  hold_days,
                "reason":     reason,
            })

    if updated:
        save_json(KR_TRADES_FILE, trades)


def run_kr_scan():
    log.info(f"=== KR 스캔 시작 | {market_status()} ===")

    if not is_kr_market_open():
        log.info("장외 시간 — 스캔 스킵")
        update_journal({"_type":"scan","time":datetime.now().strftime("%H:%M:%S"),
                        "status":"장외","signals":[]})
        return

    cfg       = load_json(KR_STRAT_FILE, {
        "drop_threshold": -3.0,
        "rsi_threshold":  35,
        "relative_drop":  -2.0,
        "vol_ratio_min":  1.5,
        "bb_threshold":   0.2,
        "budget_krw":     500000,
        "use_rsi":        True,
        "use_relative":   True,
        "use_volume":     True,
        "use_bb":         True,
        "watch_tickers":  [],
    })
    portfolio = load_json(KR_PORT_FILE, [])
    trades    = load_json(KR_TRADES_FILE, [])

    port_tickers  = [h["ticker"] for h in portfolio]
    watch_tickers = list(set(port_tickers + cfg.get("watch_tickers", [])))

    if not watch_tickers:
        log.warning("감시 종목 없음")
        return

    # 지수 등락
    kospi_chg  = get_kospi_change()
    kosdaq_chg = get_kosdaq_change()
    log.info(f"KOSPI: {kospi_chg:+.2f}% / KOSDAQ: {kosdaq_chg:+.2f}%" if kospi_chg else "지수 조회 실패")

    # 전체 분석
    analyses  = [r for r in (analyze_kr_ticker(t) for t in watch_tickers) if r]
    price_map = {r["ticker"]: r["curr_price"] for r in analyses}

    # ── 매도 체크 (매수 전 선행 실행)
    check_kr_sells(cfg, price_map)

    # 비중 계산
    total_val = sum(h["qty"] * price_map.get(suffix(h["ticker"]), h["avg_price"]) for h in portfolio)
    weights   = {}
    for h in portfolio:
        tk  = suffix(h["ticker"])
        val = h["qty"] * price_map.get(tk, h["avg_price"])
        weights[tk] = round(val / total_val * 100, 2) if total_val > 0 else 0

    # 조건 체크
    signals = []
    for row in analyses:
        mkt_chg = kosdaq_chg if row["market"] == "KOSDAQ" else kospi_chg
        passed, conds = check_kr_conditions(row, cfg, mkt_chg)
        row["weight_%"] = weights.get(row["ticker"], 0)
        row["passed"]   = passed
        row["conds"]    = {k: v[1] for k, v in conds.items()}
        if passed:
            signals.append(row)
            log.info(f"  ✅ {row['ticker']} {row['name']} | "
                     f"낙폭{row['change_pct']:+.2f}% RSI{row['rsi']} "
                     f"거래량{row['vol_ratio']:.1f}x %B{row['bb_pct']:.2f}")

    update_journal({
        "_type":   "scan",
        "time":    datetime.now().strftime("%H:%M:%S"),
        "status":  "장중",
        "kospi":   kospi_chg,
        "kosdaq":  kosdaq_chg,
        "scanned": len(analyses),
        "signals": [{"ticker":r["ticker"],"name":r["name"],
                     "change_pct":r["change_pct"],"rsi":r["rsi"],
                     "vol_ratio":r["vol_ratio"]} for r in signals],
    })

    if not signals:
        log.info("신호 없음")
        return

    # 중복 매수 방지
    today_str    = date.today().isoformat()
    traded_today = {t["ticker"] for t in trades if t.get("date","").startswith(today_str)}
    new_signals  = [s for s in signals if s["ticker"] not in traded_today]
    if not new_signals:
        log.info("오늘 이미 매수 — 스킵")
        return

    # 매수 대상: 비중 낮고 낙폭 큰 종목
    port_signals = [s for s in new_signals if s["ticker"] in [suffix(h["ticker"]) for h in portfolio]]
    if port_signals:
        for s in port_signals:
            s["score"] = (1 - s["weight_%"] / 100) * 0.5 + \
                         (-s["change_pct"] / 30)   * 0.3 + \
                         (1 - s["bb_pct"])          * 0.2
        target = sorted(port_signals, key=lambda x: x["score"], reverse=True)[0]
        reason = f"리밸런싱 (비중{target['weight_%']:.1f}% 낙폭{target['change_pct']:+.2f}% %B{target['bb_pct']:.2f})"
    else:
        target = sorted(new_signals, key=lambda x: x["change_pct"])[0]
        reason = f"감시종목 최대낙폭 ({target['change_pct']:+.2f}%)"

    # 매수 기록
    exec_price  = target["curr_price"]
    budget_krw  = cfg["budget_krw"]
    exec_qty    = max(1, int(budget_krw / exec_price))
    amount_krw  = exec_price * exec_qty

    new_trade = {
        "id":           len(trades) + 1,
        "date":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action":       "BUY",
        "ticker":       target["ticker"],
        "name":         target["name"],
        "market":       target["market"],
        "price":        exec_price,
        "qty":          exec_qty,
        "amount_krw":   amount_krw,
        "rsi_at_buy":   target["rsi"],
        "drop_pct":     target["change_pct"],
        "drop_52w":     target["drop_52w"],
        "vol_ratio":    target["vol_ratio"],
        "bb_pct":       target["bb_pct"],
        "kospi_at_buy": kospi_chg,
        "reason":       reason,
        "memo":         f"자동매수 | {reason}",
        "status":       "open",
        "sell_price":   None,
        "pnl_krw":      None,
    }
    trades.append(new_trade)
    save_json(KR_TRADES_FILE, trades)

    update_journal({
        "_type":      "trade",
        "time":       datetime.now().strftime("%H:%M:%S"),
        "ticker":     target["ticker"],
        "name":       target["name"],
        "market":     target["market"],
        "price":      exec_price,
        "qty":        exec_qty,
        "amount_krw": amount_krw,
        "rsi":        target["rsi"],
        "change_pct": target["change_pct"],
        "vol_ratio":  target["vol_ratio"],
        "bb_pct":     target["bb_pct"],
        "kospi":      kospi_chg,
        "reason":     reason,
        "conditions": target["conds"],
    })

    log.info(f"  🛒 자동매수: {target['ticker']} {target['name']} "
             f"{exec_qty}주 @ ₩{exec_price:,} = ₩{amount_krw:,} | {reason}")

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("국내 주식 페이퍼 매매 자동 트레이더 시작")
    log.info("=" * 60)

    run_kr_scan()

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_kr_scan, "interval", minutes=5, id="kr_scan")
    log.info("스케줄러 시작 — 5분마다 스캔 (KST 09:00~15:30)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("트레이더 종료")
