#!/bin/bash
# 자동매매 봇 watchdog — crash 시 자동 재시작
# WSL 부팅 시 자동 실행됨 (/etc/wsl.conf 설정)

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$BASE_DIR/data"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 자동매매 watchdog 시작" >> "$LOG_DIR/watchdog.log"

# 미국 봇 watchdog
us_watchdog() {
    while true; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [US] 봇 시작" >> "$LOG_DIR/watchdog.log"
        python3 "$BASE_DIR/auto_trader.py" >> "$LOG_DIR/auto_trader.log" 2>&1
        EXIT_CODE=$?
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [US] 봇 종료 (exit=$EXIT_CODE) — 10초 후 재시작" >> "$LOG_DIR/watchdog.log"
        sleep 10
    done
}

# 국내 봇 watchdog
kr_watchdog() {
    while true; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [KR] 봇 시작" >> "$LOG_DIR/watchdog.log"
        python3 "$BASE_DIR/auto_trader_kr.py" >> "$LOG_DIR/auto_trader_kr.log" 2>&1
        EXIT_CODE=$?
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [KR] 봇 종료 (exit=$EXIT_CODE) — 10초 후 재시작" >> "$LOG_DIR/watchdog.log"
        sleep 10
    done
}

# 두 봇을 백그라운드로 실행
us_watchdog &
US_PID=$!
kr_watchdog &
KR_PID=$!

echo "[$(date '+%Y-%m-%d %H:%M:%S')] US watchdog PID=$US_PID / KR watchdog PID=$KR_PID" >> "$LOG_DIR/watchdog.log"

# 두 프로세스가 살아있는 한 대기
wait $US_PID $KR_PID
