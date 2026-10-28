#!/usr/bin/env bash
#
# run.sh — start / restart the Mission 2026 WhatsApp bot.
#
#   ./run.sh            start it (or restart if already running), in the foreground
#   ./run.sh start      same as above
#   ./run.sh stop       stop the bot and its Chrome session
#   ./run.sh restart    stop, then start
#   ./run.sh status     show whether it is running and what it reports
#   ./run.sh logs       follow the log file
#   ./run.sh bg         start in the background (survives closing the terminal)
#
# It takes care of the things that otherwise cause a silent startup failure:
# stale node processes, a leftover Chrome SingletonLock, and a missing DISPLAY.
#
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")" || exit 1

BOT_DIR="$(pwd)"
LOG_FILE="${BOT_DIR}/bot.log"
PID_FILE="${BOT_DIR}/bot.pid"
AUTH_DIR="${BOT_DIR}/.wwebjs_auth"
PORT="${PORT:-3000}"

# ---------------------------------------------------------------- helpers
c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m%s\033[0m\n' "$*"; }
c_err()  { printf '\033[31m%s\033[0m\n' "$*"; }
c_info() { printf '\033[36m%s\033[0m\n' "$*"; }

bot_pids() {
  ps -eo pid,args 2>/dev/null \
    | grep -E "node .*index\.js|node index\.js" \
    | grep -v grep \
    | awk '{print $1}'
}

chrome_pids() {
  ps -eo pid,args 2>/dev/null \
    | grep -E "chrome|chromium" \
    | grep "wwebjs_auth" \
    | grep -v grep \
    | awk '{print $1}'
}

is_running() { [ -n "$(bot_pids)" ]; }

# ---------------------------------------------------------------- stop
do_stop() {
  local pids
  pids="$(bot_pids)"
  if [ -z "$pids" ]; then
    c_warn "Bot is not running."
  else
    c_info "Stopping bot (pids: $(echo "$pids" | tr '\n' ' '))…"
    # SIGTERM first so Chrome/the session can close cleanly, then SIGKILL.
    echo "$pids" | xargs -r kill 2>/dev/null
    sleep 2
    pids="$(bot_pids)"
    [ -n "$pids" ] && echo "$pids" | xargs -r kill -9 2>/dev/null
  fi

  # Chrome instances holding the WhatsApp session lock
  pids="$(chrome_pids)"
  if [ -n "$pids" ]; then
    c_info "Stopping leftover Chrome session…"
    echo "$pids" | xargs -r kill -9 2>/dev/null
    sleep 1
  fi

  # A leftover lock makes the next launch hang at "loading 100%".
  if [ -d "$AUTH_DIR" ]; then
    find "$AUTH_DIR" -name "SingletonLock" -delete 2>/dev/null
  fi

  rm -f "$PID_FILE"
  c_ok "Stopped."
}

# ---------------------------------------------------------------- preflight
preflight() {
  local fail=0

  if ! command -v node >/dev/null 2>&1; then
    c_err "node is not installed (need Node 18+)."
    fail=1
  fi

  if [ ! -f ".env" ]; then
    c_err ".env not found. Copy .env.example and fill it in."
    fail=1
  fi

  if [ ! -d "node_modules" ]; then
    c_warn "node_modules missing — running 'npm install'…"
    npm install || { c_err "npm install failed."; fail=1; }
  fi

  # Chrome is what drives WhatsApp Web; without it nothing starts.
  if [ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]; then
    for b in google-chrome google-chrome-stable chromium chromium-browser; do
      if command -v "$b" >/dev/null 2>&1; then
        export PUPPETEER_EXECUTABLE_PATH="$(command -v "$b")"
        break
      fi
    done
  fi
  if [ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]; then
    c_err "No Chrome/Chromium found. Install google-chrome, or set PUPPETEER_EXECUTABLE_PATH."
    fail=1
  else
    c_info "Chrome: ${PUPPETEER_EXECUTABLE_PATH}"
  fi

  # GUI control commands (!screen, !open, !key …) need an X display.
  if [ -z "${DISPLAY:-}" ]; then
    export DISPLAY=":0"
    c_warn "DISPLAY was unset — defaulting to :0 (GUI commands need a real display)."
  fi

  # !task talks to opencode — without it on PATH that command can't work.
  if ! command -v opencode >/dev/null 2>&1; then
    for d in "$HOME/.opencode/bin" "$HOME/.local/bin"; do
      [ -x "$d/opencode" ] && export PATH="$d:$PATH" && break
    done
  fi
  if command -v opencode >/dev/null 2>&1; then
    c_info "opencode: $(command -v opencode)"
  else
    c_warn "opencode not found on PATH — !task won't work (add ~/.opencode/bin to PATH)."
  fi

  return $fail
}

# ---------------------------------------------------------------- start
do_start_bg() {
  preflight || return 1
  do_stop >/dev/null 2>&1

  if is_running; then
    c_err "Something is still holding the bot process. Try: ./run.sh stop"
    return 1
  fi

  if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
    c_warn "Port ${PORT} is already in use by another process:"
    lsof -i tcp:"$PORT" | sed -n '2,4p'
    c_warn "Continuing — if the bot fails to bind, stop that process first."
  fi

  c_info "Starting bot in the background… (log: ${LOG_FILE})"
  : > "$LOG_FILE"
  nohup node index.js >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  c_info "Waiting for it to come up…"
  for _ in $(seq 1 45); do
    if grep -qE "Client is ready|status.*ready" "$LOG_FILE" 2>/dev/null; then
      c_ok "Bot is READY."
      do_status
      return 0
    fi
    if ! is_running; then
      c_err "Bot exited during startup. Last lines of the log:"
      tail -25 "$LOG_FILE"
      return 1
    fi
    sleep 1
  done

  c_warn "Still starting after 45s — it may be waiting on the QR scan."
  do_status
}

do_start_fg() {
  preflight || return 1
  do_stop >/dev/null 2>&1

  c_info "Starting bot in the foreground. Press Ctrl-C to stop."
  c_info "If a QR code is printed, scan it with WhatsApp → Linked devices."
  echo
  node index.js
}

# ---------------------------------------------------------------- status
do_status() {
  if is_running; then
    c_ok "Bot process running (pid: $(bot_pids | tr '\n' ' '))"
  else
    c_warn "Bot process NOT running."
  fi

  local resp
  resp="$(curl -s --max-time 5 "http://127.0.0.1:${PORT}/status" 2>/dev/null)"
  if [ -n "$resp" ]; then
    c_ok "HTTP ${PORT}/status → ${resp}"
  else
    c_warn "HTTP ${PORT}/status did not answer (not ready, or port ${PORT} is taken)."
  fi

  local django
  django="$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:8001/api/habits/" 2>/dev/null)"
  if [ "$django" = "200" ]; then
    c_ok "Mission 2026 API :8001 reachable (habit sync will work)."
  else
    c_warn "Mission 2026 API :8001 not answering (HTTP ${django:-none}) — check-ins will queue, not save."
  fi
}

# ---------------------------------------------------------------- main
case "${1:-start}" in
  start)
    do_start_fg
    ;;
  bg|background|daemon)
    do_start_bg
    ;;
  stop)
    do_stop
    ;;
  restart)
    do_stop
    do_start_fg
    ;;
  restart-bg)
    do_stop
    do_start_bg
    ;;
  status)
    do_status
    ;;
  logs|log)
    if [ -f "$LOG_FILE" ]; then
      tail -n 50 -f "$LOG_FILE"
    else
      c_warn "No log yet (${LOG_FILE}). Start with './run.sh bg' to use logs."
    fi
    ;;
  *)
    cat <<EOF
Mission 2026 WhatsApp bot

  ./run.sh              start in the foreground (Ctrl-C stops it)
  ./run.sh bg           start in the background, with a log file
  ./run.sh stop         stop the bot + its Chrome session
  ./run.sh restart      stop, then start (foreground)
  ./run.sh restart-bg   stop, then start (background)
  ./run.sh status       running? + bot and Django health
  ./run.sh logs         follow bot.log

Notes
  - First run: open WhatsApp → Linked devices → Link a device, and scan the QR.
  - Kill/restart safely with this script; don't 'pkill node' (it can hit the editor).
  - The Django server must be up for check-ins to save; otherwise they queue.
EOF
    ;;
esac
