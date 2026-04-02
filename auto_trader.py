"""
auto_trader.py — 페이퍼 매매 자동 실행 엔진
- 5분마다 조건 체크 (미국 장 시간: ET 09:30~16:00)
- 조건 충족 시 자동 매수 기록
- data/journal/YYYY-MM-DD.json 일지 업데이트
실행: python3 auto_trader.py
"""
import os, sys, json, time, logging
from datetime import datetime, date
import numpy as np
import pytz
import yfinance as yf
from apscheduler.schedulers.blocking import BlockingScheduler
from utils.notify import send_telegram

# ── 경로 설정 ─────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(BASE_DIR, "data")
JOURNAL_DIR    = os.path.join(DATA_DIR, "journal")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
TRADES_FILE    = os.path.join(DATA_DIR, "paper_trades.json")
STRATEGY_FILE  = os.path.join(DATA_DIR, "strategy_config.json")
LOG_FILE       = os.path.join(DATA_DIR, "auto_trader.log")
os.makedirs(JOURNAL_DIR, exist_ok=True)

# ── 로깅 설정 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("auto_trader")

# ── JSON 헬퍼 ─────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 미국 장 시간 체크 ─────────────────────────────────────────
def is_market_open() -> bool:
    """미국 동부시간 기준 09:30~16:00, 평일만"""
    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)
    if now_et.weekday() >= 5:  # 토·일
        return False
    market_open  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now_et <= market_close

def market_status() -> str:
    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)
    kst    = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)
    return (f"ET {now_et.strftime('%H:%M')} / KST {now_kst.strftime('%H:%M')} "
            f"({'장중' if is_market_open() else '장외'})")

# ── VIX 조회 ─────────────────────────────────────────────────
def get_vix() -> float | None:
    try:
        hist = yf.Ticker("^VIX").history(period="2d")
        return round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
    except:
        return None

# ── 종목 분석 ─────────────────────────────────────────────────
def analyze_ticker(ticker: str) -> dict | None:
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period="1y", interval="1d")
        if len(hist) < 20:
            return None
        hist.index = hist.index.tz_localize(None)

        prev  = hist["Close"].iloc[-2]
        curr  = hist["Close"].iloc[-1]
        chg   = (curr - prev) / prev * 100
        h52   = hist["Close"].max()
        d52   = (curr - h52) / h52 * 100

        delta = hist["Close"].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi_s = 100 - (100 / (1 + rs))
        rsi   = float(rsi_s.iloc[-1]) if not rsi_s.empty else None

        ma20     = float(hist["Close"].rolling(20).mean().iloc[-1])
        ma20_gap = (curr - ma20) / ma20 * 100

        info = t.info
        return {
            "ticker":    ticker,
            "name":      info.get("shortName", ticker),
            "curr_price": round(curr, 2),
            "change_pct": round(chg, 2),
            "high_52w":   round(h52, 2),
            "drop_52w":   round(d52, 2),
            "rsi":        round(rsi, 1) if rsi else None,
            "ma20_gap":   round(ma20_gap, 2),
        }
    except Exception as e:
        log.warning(f"{ticker} 분석 실패: {e}")
        return None

# ── 조건 체크 ─────────────────────────────────────────────────
def check_conditions(row: dict, cfg: dict) -> tuple[bool, dict]:
    results = {}
    results["당일 낙폭"] = (
        row["change_pct"] <= cfg["drop_threshold"],
        f"{row['change_pct']:+.2f}% (기준 {cfg['drop_threshold']:.1f}%)"
    )
    if cfg.get("use_rsi", True) and row["rsi"] is not None:
        results["RSI"] = (
            row["rsi"] <= cfg["rsi_threshold"],
            f"RSI={row['rsi']:.1f} (기준 ≤{cfg['rsi_threshold']})"
        )
    if cfg.get("use_52w", True):
        results["52주 낙폭"] = (
            row["drop_52w"] <= cfg["high52w_drop"],
            f"{row['drop_52w']:+.2f}% (기준 ≤{cfg['high52w_drop']:.0f}%)"
        )
    passed = all(v[0] for v in results.values())
    return passed, results

# ── 일지 업데이트 ─────────────────────────────────────────────
def update_journal(entry: dict):
    today      = date.today().isoformat()
    jfile      = os.path.join(JOURNAL_DIR, f"{today}.json")
    journal    = load_json(jfile, {"date": today, "scans": [], "trades": [], "summary": {}})
    entry_type = entry.pop("_type", "scan")
    journal[entry_type + "s"].append(entry)

    # 당일 요약 업데이트
    trades_today = journal["trades"]
    journal["summary"] = {
        "total_scans":    len(journal["scans"]),
        "total_trades":   len(trades_today),
        "total_invested": sum(t["amount_usd"] for t in trades_today),
        "tickers_traded": list({t["ticker"] for t in trades_today}),
        "last_updated":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(jfile, journal)

# ── 매도 체크 ─────────────────────────────────────────────────
def check_sells(cfg: dict, price_map: dict):
    """open 포지션 중 익절/손절/기간청산 조건 충족 시 자동 매도 기록"""
    trades = load_json(TRADES_FILE, [])
    open_trades = [t for t in trades if t.get("status") == "open"]
    if not open_trades:
        return

    tp  = cfg.get("take_profit_pct", 7.0)
    sl  = cfg.get("stop_loss_pct", -5.0)
    mhd = cfg.get("max_hold_days", 20)
    updated = False

    for t in open_trades:
        curr = price_map.get(t["ticker"])
        if curr is None:
            try:
                hist = yf.Ticker(t["ticker"]).history(period="2d")
                curr = float(hist["Close"].iloc[-1]) if not hist.empty else None
            except Exception:
                pass
        if curr is None:
            continue

        buy_price = t["price"]
        pnl_pct   = (curr - buy_price) / buy_price * 100

        # 보유 일수
        try:
            buy_dt   = datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S")
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

        # RSI 과매수 청산
        rsi_exit = cfg.get("rsi_exit_threshold", 65)
        if cfg.get("use_rsi_exit", True):
            try:
                hist_rsi = yf.Ticker(t["ticker"]).history(period="1mo")
                delta = hist_rsi["Close"].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_now = float((100 - 100/(1+rs)).iloc[-1])
                if rsi_now >= rsi_exit and not reason:
                    reason = f"RSI 과매수 청산 (RSI={rsi_now:.1f} ≥ {rsi_exit})"
            except Exception:
                pass

        if reason:
            pnl_usd = round((curr - buy_price) * t["qty"], 2)
            t["status"]     = "closed"
            t["sell_price"] = round(curr, 2)
            t["sell_date"]  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t["pnl_usd"]    = pnl_usd
            t["pnl_pct"]    = round(pnl_pct, 2)
            t["sell_reason"]= reason
            updated = True
            log.info(f"  💰 자동매도: {t['ticker']} {t['qty']}주 "
                     f"@ ${curr:.2f} | PnL ${pnl_usd:+.2f} ({pnl_pct:+.2f}%) | {reason}")
            send_telegram(f"💰 [자동매도] {t['ticker']} @ ${curr:.2f}\n"
                          f"손익: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%) | 사유: {reason}")
            update_journal({
                "_type":       "trade",
                "action":      "SELL",
                "time":        datetime.now().strftime("%H:%M:%S"),
                "ticker":      t["ticker"],
                "name":        t.get("name", t["ticker"]),
                "price":       curr,
                "qty":         t["qty"],
                "amount_usd":  round(curr * t["qty"], 2),
                "pnl_usd":     pnl_usd,
                "pnl_pct":     round(pnl_pct, 2),
                "hold_days":   hold_days,
                "reason":      reason,
            })

    if updated:
        save_json(TRADES_FILE, trades)


# ── 메인 스캔 함수 ────────────────────────────────────────────
def run_scan():
    log.info(f"=== 스캔 시작 | {market_status()} ===")

    if not is_market_open():
        log.info("장외 시간 — 스캔 스킵")
        # 장외에도 스캔 기록은 남김
        update_journal({
            "_type": "scan",
            "time":   datetime.now().strftime("%H:%M:%S"),
            "status": "장외",
            "signals": [],
        })
        return

    cfg       = load_json(STRATEGY_FILE, {
        "drop_threshold": -3.0, "rsi_threshold": 40,
        "high52w_drop": -20.0,  "vix_caution": 25,
        "vix_half": 30,         "budget_usd": 1000,
        "use_rsi": True,        "use_52w": True,
        "use_vix": True,        "watch_tickers": [],
        "use_rsi_exit": True,   "rsi_exit_threshold": 65,
    })
    portfolio = load_json(PORTFOLIO_FILE, [])
    trades    = load_json(TRADES_FILE, [])

    port_tickers  = [h["ticker"] for h in portfolio]
    watch_tickers = list(set(port_tickers + cfg.get("watch_tickers", [])))

    if not watch_tickers:
        log.warning("감시 종목 없음")
        return

    # VIX 체크
    vix_val = get_vix()
    if vix_val:
        if cfg.get("use_vix") and vix_val >= cfg["vix_half"]:
            actual_budget = cfg["budget_usd"] * 0.5
            vix_status    = f"공황({vix_val})"
        elif cfg.get("use_vix") and vix_val >= cfg["vix_caution"]:
            actual_budget = cfg["budget_usd"] * 0.75
            vix_status    = f"주의({vix_val})"
        else:
            actual_budget = cfg["budget_usd"]
            vix_status    = f"정상({vix_val})"
    else:
        actual_budget = cfg["budget_usd"]
        vix_status    = "조회실패"

    log.info(f"VIX: {vix_status} | 예산: ${actual_budget:.0f} | 감시 {len(watch_tickers)}종목")

    # 전체 비중 계산
    analyses  = [r for r in (analyze_ticker(t) for t in watch_tickers) if r]
    price_map = {r["ticker"]: r["curr_price"] for r in analyses}

    # ── 매도 체크 (매수 전 선행 실행)
    check_sells(cfg, price_map)
    total_val = sum(h["qty"] * price_map.get(h["ticker"], h["avg_price"]) for h in portfolio)
    weights   = {
        h["ticker"]: round(h["qty"] * price_map.get(h["ticker"], h["avg_price"]) / total_val * 100, 2)
        for h in portfolio
    } if total_val > 0 else {}

    # 조건 체크
    signals = []
    for row in analyses:
        passed, conds = check_conditions(row, cfg)
        row["weight_%"] = weights.get(row["ticker"], 0)
        row["passed"]   = passed
        row["conds"]    = {k: v[1] for k, v in conds.items()}
        if passed:
            signals.append(row)
            log.info(f"  ✅ 신호: {row['ticker']} | {row['change_pct']:+.2f}% RSI={row['rsi']} 52w={row['drop_52w']:+.1f}%")

    # 스캔 기록
    update_journal({
        "_type":   "scan",
        "time":    datetime.now().strftime("%H:%M:%S"),
        "status":  "장중",
        "vix":     vix_val,
        "scanned": len(analyses),
        "signals": [
            {"ticker": r["ticker"], "change_pct": r["change_pct"],
             "rsi": r["rsi"], "drop_52w": r["drop_52w"]}
            for r in signals
        ],
    })

    if not signals:
        log.info("신호 없음")
        return

    # 중복 매수 방지: 오늘 이미 매수한 종목 제외
    today_str     = date.today().isoformat()
    traded_today  = {t["ticker"] for t in trades
                     if t.get("date", "").startswith(today_str)}

    new_signals = [s for s in signals if s["ticker"] not in traded_today]
    if not new_signals:
        log.info("오늘 이미 매수한 종목 — 중복 스킵")
        return

    # 매수 대상: 비중 낮고 낙폭 큰 종목 (리밸런싱)
    port_signals = [s for s in new_signals if s["ticker"] in port_tickers]
    if port_signals:
        for s in port_signals:
            s["score"] = (1 - s["weight_%"] / 100) * 0.6 + (-s["change_pct"] / 100) * 0.4
        target = sorted(port_signals, key=lambda x: x["score"], reverse=True)[0]
        reason = f"리밸런싱 (비중{target['weight_%']:.1f}% 낙폭{target['change_pct']:+.2f}%)"
    else:
        target = sorted(new_signals, key=lambda x: x["change_pct"])[0]
        reason = f"감시종목 최대낙폭 ({target['change_pct']:+.2f}%)"

    # 매수 기록
    exec_price = target["curr_price"]
    exec_qty   = round(actual_budget / exec_price, 4)
    new_trade  = {
        "id":            len(trades) + 1,
        "date":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action":        "BUY",
        "ticker":        target["ticker"],
        "name":          target["name"],
        "price":         exec_price,
        "qty":           exec_qty,
        "amount_usd":    round(exec_price * exec_qty, 2),
        "rsi_at_buy":    target["rsi"],
        "drop_pct":      target["change_pct"],
        "drop_52w":      target["drop_52w"],
        "vix_at_buy":    vix_val,
        "select_reason": reason,
        "memo":          f"자동매수 | {reason}",
        "status":        "open",
        "sell_price":    None,
        "pnl_usd":       None,
    }
    trades.append(new_trade)
    save_json(TRADES_FILE, trades)

    # 일지 기록
    update_journal({
        "_type":         "trade",
        "time":          datetime.now().strftime("%H:%M:%S"),
        "ticker":        target["ticker"],
        "name":          target["name"],
        "price":         exec_price,
        "qty":           exec_qty,
        "amount_usd":    new_trade["amount_usd"],
        "rsi":           target["rsi"],
        "change_pct":    target["change_pct"],
        "drop_52w":      target["drop_52w"],
        "vix":           vix_val,
        "vix_status":    vix_status,
        "reason":        reason,
        "conditions":    target["conds"],
    })

    log.info(f"  🛒 자동매수: {target['ticker']} {exec_qty}주 @ ${exec_price:.2f} "
             f"= ${new_trade['amount_usd']:.0f} | {reason}")
    send_telegram(f"🛒 [자동매수] {target['ticker']} {exec_qty:.2f}주 @ ${exec_price:.2f}\n"
                  f"금액: ${new_trade['amount_usd']:.0f} | RSI: {target['rsi']} | VIX: {vix_val}\n"
                  f"사유: {reason}")

# ── 스케줄러 실행 ─────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 60)
    log.info("페이퍼 매매 자동 트레이더 시작")
    log.info(f"전략 파일: {STRATEGY_FILE}")
    log.info(f"거래 파일: {TRADES_FILE}")
    log.info(f"일지 경로: {JOURNAL_DIR}")
    log.info("=" * 60)

    # 시작 즉시 1회 실행
    run_scan()

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_scan, "interval", minutes=5, id="scan")
    log.info("스케줄러 시작 — 5분마다 스캔 (미국 장 중에만 매수)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("트레이더 종료")
