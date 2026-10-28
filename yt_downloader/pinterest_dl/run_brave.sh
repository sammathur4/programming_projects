#!/usr/bin/env bash
# Launch Brave headless on the user's real profile and run a scraper against it.
#
# Usage:
#   bash run_brave.sh [scraper.js] [out.json]
#
# Defaults to pull_pins.js -> pins.json, both next to this script.
# Requires: Brave fully quit (profile lock) and already logged into Pinterest.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JS="${1:-$HERE/pull_pins.js}"
OUT="${2:-$HERE/pins.json}"
PROFILE="$HOME/.config/BraveSoftware/Brave-Browser"
LOG="$HERE/brave.log"

# Wait up to 30s for Brave to fully exit (profile lock is released on quit).
for i in $(seq 1 30); do
  if ! pgrep -x brave >/dev/null 2>&1 && ! pgrep -f "Brave-Browser" >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 1 ]; then
    echo "Waiting for Brave to exit..." >&2
  fi
  sleep 1
done

if pgrep -x brave >/dev/null 2>&1 || pgrep -f "Brave-Browser" >/dev/null 2>&1; then
  echo "ERROR: Brave still running after 30s. Fully quit Brave (check the tray) and retry." >&2
  exit 2
fi

pkill -f "remote-debugging-port=9333" 2>/dev/null || true
sleep 1

nohup /usr/bin/brave-browser \
  --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
  --remote-debugging-port=9333 \
  --user-data-dir="$PROFILE" \
  --window-size=1600,1200 \
  about:blank > "$LOG" 2>&1 &
BPID=$!
# Give Brave time to boot and attach the debugger.
for i in $(seq 1 20); do
  if curl -s --max-time 1 "http://127.0.0.1:9333/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
sleep 3

node "$JS" > "$OUT" 2>"${OUT%.json}.err"
echo "node_exit=$?"

kill $BPID 2>/dev/null || true
sleep 1
pkill -f "remote-debugging-port=9333" 2>/dev/null || true
wc -c "$OUT" "${OUT%.json}.err"
