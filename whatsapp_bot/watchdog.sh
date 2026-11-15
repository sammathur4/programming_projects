#!/usr/bin/env bash
set -uo pipefail

BOT_DIR="$(dirname "$(readlink -f "$0")")"
PID_FILE="$BOT_DIR/watchdog.pid"
LOG_FILE="$BOT_DIR/watchdog.log"
INTERVAL="${WATCHDOG_INTERVAL:-60}"

bot_running() {
  ps -eo args= | awk '$1 == "node" && $0 ~ /index[.]js/ { found=1 } END { exit !found }'
}

case "${1:-start}" in
  run)
    echo "$$" > "$PID_FILE"
    trap 'rm -f "$PID_FILE"' EXIT
    while :; do
      if bot_running; then
        printf '%s bot running\n' "$(date --iso-8601=seconds)" >> "$LOG_FILE"
      else
        printf '%s bot missing; starting\n' "$(date --iso-8601=seconds)" >> "$LOG_FILE"
        bash "$BOT_DIR/run.sh" bg >> "$BOT_DIR/bot.log" 2>&1
        result=$?
        printf '%s start exited (%s)\n' "$(date --iso-8601=seconds)" "$result" >> "$LOG_FILE"
      fi
      sleep "$INTERVAL"
    done
    ;;
  start)
    if [[ -r "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
      echo "Watchdog already running (pid $(<"$PID_FILE"))."
      exit 0
    fi
    nohup bash "$BOT_DIR/watchdog.sh" run >> "$LOG_FILE" 2>&1 </dev/null &
    echo $! > "$PID_FILE"
    echo "Watchdog started (pid $!)."
    ;;
  stop)
    if [[ -r "$PID_FILE" ]] && kill "$(<"$PID_FILE")" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "Watchdog stopped."
    else
      rm -f "$PID_FILE"
      echo "Watchdog is not running."
    fi
    ;;
  status)
    if [[ -r "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
      echo "Watchdog running (pid $(<"$PID_FILE"))."
    else
      echo "Watchdog not running."
    fi
    if bot_running; then echo "Bot process running."; else echo "Bot process not running."; fi
    ;;
  logs)
    touch "$LOG_FILE"
    tail -n 50 -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: bash watchdog.sh {start|stop|status|logs}"
    exit 2
    ;;
esac
