#!/bin/bash
# WSL 시작 시 자동 실행 스크립트
# ~/.bashrc 또는 ~/.profile에 추가:
#   nohup /home/lyjan/stock-analysis-platform/start_on_boot.sh > /dev/null 2>&1 &

SCRIPT_DIR="/home/lyjan/stock-analysis-platform"
VENV_PYTHON="/home/lyjan/venv/bin/python"
LOG_DIR="$SCRIPT_DIR/data"

# 이미 실행 중이면 스킵
if pgrep -f "auto_trader.py" > /dev/null; then
    echo "[$(date)] 트레이더 이미 실행 중" >> "$LOG_DIR/watchdog.log"
    exit 0
fi

echo "[$(date)] WSL 부팅 시 트레이더 자동 시작" >> "$LOG_DIR/watchdog.log"

cd "$SCRIPT_DIR"

# US 트레이더
nohup "$VENV_PYTHON" "$SCRIPT_DIR/auto_trader.py" >> "$LOG_DIR/auto_trader.log" 2>&1 &
echo "[$(date)] US 트레이더 시작 PID=$!" >> "$LOG_DIR/watchdog.log"

sleep 2

# KR 트레이더
nohup "$VENV_PYTHON" "$SCRIPT_DIR/auto_trader_kr.py" >> "$LOG_DIR/auto_trader_kr.log" 2>&1 &
echo "[$(date)] KR 트레이더 시작 PID=$!" >> "$LOG_DIR/watchdog.log"
