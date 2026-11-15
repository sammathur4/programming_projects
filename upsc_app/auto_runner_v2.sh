#!/bin/bash

# Autonomous Agent Runner v2 for OpenCode
WORKDIR="/media/saksham/phone data/programming_projects/upsc_app"
LOG_DIR="$WORKDIR/logs"
STATE_DIR="$WORKDIR/.agent_state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

# Model fallback chain
MODELS=(
  "opencode-go/iceman-contributor-free"
  "opencode-go/glm-5.3-flash"
  "opencode-go/deepseek-v4.1-flash"
  "opencode-go/qwen3.8-flash"
  "opencode-go/kimi-k2.7-code"
)

SLEEP_NORMAL=300
SLEEP_RATE_LIMIT=900
SLEEP_ERROR=180

STATE_FILE="$STATE_DIR/runner_state.json"
SESSION_FILE="$STATE_DIR/current_session.txt"

# Initialize state
if [ ! -f "$STATE_FILE" ]; then
  echo '{"iteration": 0, "model_index": 0, "consecutive_errors": 0}' > "$STATE_FILE"
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/auto_runner.log"
}

get_state() {
  python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('$1',0))"
}

set_state() {
  python3 -c "
import json
d=json.load(open('$STATE_FILE'))
d['$1']=$2
json.dump(d, open('$STATE_FILE','w'))
"
}

while true; do
  ITERATION=$(get_state iteration)
  ITERATION=$((ITERATION + 1))
  set_state iteration $ITERATION
  
  MODEL_INDEX=$(get_state model_index)
  CURRENT_MODEL="${MODELS[$MODEL_INDEX]}"
  
  LOG_FILE="$LOG_DIR/iter_${ITERATION}_$(date +%Y%m%d_%H%M%S).log"
  
  log "=== Iteration $ITERATION | Model: $CURRENT_MODEL ==="
  
  cd "$WORKDIR" || continue
  
  # Check if we have a session to continue
  if [ -f "$SESSION_FILE" ] && [ -s "$SESSION_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_FILE")
    log "Continuing session: $SESSION_ID"
    timeout 7200 opencode run -m "$CURRENT_MODEL" -s "$SESSION_ID" --auto "Continue from where we left off. Execute the next steps of the UPSC task systematically." 2>&1 | tee "$LOG_FILE"
  else
    log "Starting new session"
    timeout 7200 opencode run -m "$CURRENT_MODEL" --auto "Execute the UPSC CSE 2027 knowledge base task at /media/saksham/phone data/programming_projects/upsc_app/notes/upsc_notes_task.md. Work through it phase by phase following the workflow. Save all outputs to /media/saksham/phone data/programming_projects/upsc_app/notes/ with proper structure. All coding files go to /media/saksham/phone data/programming_projects/upsc_app/. Continue building the complete knowledge base systematically." 2>&1 | tee "$LOG_FILE"
    # Try to extract session ID if possible (opencode might output it)
    grep -oP 'session[^\s]*\s+\K[^\s]+' "$LOG_FILE" | head -1 > "$SESSION_FILE" 2>/dev/null
  fi
  
  EXIT_CODE=${PIPESTATUS[0]}
  log "Exit: $EXIT_CODE"
  
  # Detect issues
  if grep -qiE "rate.*limit|quota.*exceeded|429|too many" "$LOG_FILE"; then
    log "RATE LIMIT - switching model"
    MODEL_INDEX=$(( (MODEL_INDEX + 1) % ${#MODELS[@]} ))
    set_state model_index $MODEL_INDEX
    set_state consecutive_errors 0
    sleep $SLEEP_RATE_LIMIT
    continue
  fi
  
  if grep -qiE "error|failed|exception" "$LOG_FILE" && [ $EXIT_CODE -ne 0 ]; then
    ERR_COUNT=$(get_state consecutive_errors)
    ERR_COUNT=$((ERR_COUNT + 1))
    set_state consecutive_errors $ERR_COUNT
    if [ $ERR_COUNT -ge 3 ]; then
      log "Too many errors, switching model"
      MODEL_INDEX=$(( (MODEL_INDEX + 1) % ${#MODELS[@]} ))
      set_state model_index $MODEL_INDEX
      set_state consecutive_errors 0
    fi
    sleep $SLEEP_ERROR
    continue
  fi
  
  set_state consecutive_errors 0
  log "Sleeping $SLEEP_NORMAL seconds"
  sleep $SLEEP_NORMAL
done
