#!/bin/bash

# Autonomous Agent Runner for Laxmikanth Polity Notes Generation
WORKDIR="/media/saksham/phone data/programming_projects/upsc_app"
LOG_DIR="$WORKDIR/logs/laxmikanth"
STATE_DIR="$WORKDIR/.agent_state_laxmikanth"
mkdir -p "$LOG_DIR" "$STATE_DIR"

# Model fallback chain
MODELS=(
  "opencode-go/iceman-contributor-free"
)

# old_models = ( "opencode-go/glm-5.3-flash", "opencode-go/deepseek-v4.1-flash", "opencode-go/qwen3.8-flash",  "opencode-go/kimi-k2.7-code")

SLEEP_NORMAL=300
SLEEP_RATE_LIMIT=900
SLEEP_ERROR=180

STATE_FILE="$STATE_DIR/runner_state.json"
SESSION_FILE="$STATE_DIR/current_session.txt"
PROGRESS_LOG="$LOG_DIR/progress_detailed.log"
QUESTION_LOG="$LOG_DIR/questions_asked.log"

# Initialize state
if [ ! -f "$STATE_FILE" ]; then
  echo '{"iteration": 0, "model_index": 0, "consecutive_errors": 0, "chapters_done": 0}' > "$STATE_FILE"
fi

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
  echo "$msg" | tee -a "$LOG_DIR/auto_runner.log" | tee -a "$PROGRESS_LOG"
}

log_detail() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [DETAIL] $1"
  echo "$msg" | tee -a "$PROGRESS_LOG"
}

log_question() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [QUESTION] $1"
  echo "$msg" | tee -a "$QUESTION_LOG" | tee -a "$PROGRESS_LOG"
}

log_chapter() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [CHAPTER] $1"
  echo "$msg" | tee -a "$PROGRESS_LOG"
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

log "=== LAXMIKANTH NOTES GENERATOR STARTED ==="
log "Workdir: $WORKDIR"
log "Logs: $LOG_DIR"
log "Target: /media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027/GS Paper 2 — Governance & Polity/Polity/Handbook/GS2_Laxmikanth_Chapterwise_Ultimate_Notes.md"

while true; do
  ITERATION=$(get_state iteration)
  ITERATION=$((ITERATION + 1))
  set_state iteration $ITERATION
  
  MODEL_INDEX=$(get_state model_index)
  CURRENT_MODEL="${MODELS[$MODEL_INDEX]}"
  
  LOG_FILE="$LOG_DIR/iter_${ITERATION}_$(date +%Y%m%d_%H%M%S).log"
  
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "=== Iteration $ITERATION | Model: $CURRENT_MODEL ==="
  log_detail "Session file exists=$( [ -f "$SESSION_FILE" ] && echo yes || echo no ), size=$( [ -f "$SESSION_FILE" ] && wc -c < "$SESSION_FILE" || echo 0 )"
  
  cd "$WORKDIR" || continue
  
  # Check if we have a session to continue
  if [ -f "$SESSION_FILE" ] && [ -s "$SESSION_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_FILE" | tr -d '\n\r')
    # Validate session ID format
    if [[ "$SESSION_ID" =~ ^ses ]]; then
      log "Continuing session: $SESSION_ID"
      log_detail "Starting opencode run with session continuation..."
      timeout 7200 opencode run -m "$CURRENT_MODEL" -s "$SESSION_ID" --auto "Continue generating Laxmikanth polity notes chapter by chapter. Follow the task in /media/saksham/phone data/programming_projects/upsc_app/laxmikanth_notes_task.md. Log every action: which chapter you're working on, files read/written, decisions made. If stuck or need clarification, use the question tool to ask the user questions with clear context. Be verbose in logging." 2>&1 | tee "$LOG_FILE"
    else
      log "Invalid session ID format, starting fresh session"
      rm -f "$SESSION_FILE"
      timeout 7200 opencode run -m "$CURRENT_MODEL" --auto "Start generating Laxmikanth polity notes chapter by chapter. Read the task in /media/saksham/phone data/programming_projects/upsc_app/laxmikanth_notes_task.md and execute it. Work systematically from where we left off - check the target notes file to see last chapter. Log every action: which chapter you're on, what you're reading, what you're writing. If you get stuck or need clarification on anything (scope, depth, approach, missing source), use the question tool to ask the user questions clearly. Be explicit about progress." 2>&1 | tee "$LOG_FILE"
      SESSION_EXTRACTED=$(grep -oP 'session\s+\Kses[^\s]+' "$LOG_FILE" | head -1)
      if [ -n "$SESSION_EXTRACTED" ]; then
        echo "$SESSION_EXTRACTED" > "$SESSION_FILE"
        log_detail "Extracted session ID: $SESSION_EXTRACTED"
      fi
    fi
  else
    log "Starting new session"
    log_detail "Starting fresh opencode run..."
    timeout 7200 opencode run -m "$CURRENT_MODEL" --auto "Start generating Laxmikanth polity notes chapter by chapter. Read the task in /media/saksham/phone data/programming_projects/upsc_app/laxmikanth_notes_task.md and execute it. Work systematically from where we left off - check the target notes file to see last chapter. Log every action: which chapter you're on, what you're reading, what you're writing. If you get stuck or need clarification on anything (scope, depth, approach, missing source), use the question tool to ask the user questions clearly. Be explicit about progress." 2>&1 | tee "$LOG_FILE"
    SESSION_EXTRACTED=$(grep -oP 'session\s+\Kses[^\s]+' "$LOG_FILE" | head -1)
    if [ -n "$SESSION_EXTRACTED" ]; then
      echo "$SESSION_EXTRACTED" > "$SESSION_FILE"
      log_detail "Extracted session ID: $SESSION_EXTRACTED"
    fi
  fi
  
  EXIT_CODE=${PIPESTATUS[0]}
  log "Exit code: $EXIT_CODE"
  
  # Enhanced logging - scan for important events
  log_detail "Scanning logs for progress indicators..."
  grep -n -i "chapter\|laxmikanth\|appended\|question\|stuck\|clarif" "$LOG_FILE" | tail -30 >> "$PROGRESS_LOG" 2>&1
  grep -n -A 5 -B 5 -i "question tool" "$LOG_FILE" >> "$QUESTION_LOG" 2>&1
  
  # Detect issues
  if grep -qiE "rate.*limit|quota.*exceeded|429|too many" "$LOG_FILE"; then
    log "RATE LIMIT DETECTED - switching model"
    MODEL_INDEX=$(( (MODEL_INDEX + 1) % ${#MODELS[@]} ))
    set_state model_index $MODEL_INDEX
    set_state consecutive_errors 0
    log_detail "Switched to model index $MODEL_INDEX: ${MODELS[$MODEL_INDEX]}"
    sleep $SLEEP_RATE_LIMIT
    continue
  fi
  
  if grep -qiE "error|failed|exception" "$LOG_FILE" && [ $EXIT_CODE -ne 0 ]; then
    ERR_COUNT=$(get_state consecutive_errors)
    ERR_COUNT=$((ERR_COUNT + 1))
    set_state consecutive_errors $ERR_COUNT
    log "ERROR DETECTED (count: $ERR_COUNT)"
    if [ $ERR_COUNT -ge 3 ]; then
      log "Too many consecutive errors, switching model"
      MODEL_INDEX=$(( (MODEL_INDEX + 1) % ${#MODELS[@]} ))
      set_state model_index $MODEL_INDEX
      set_state consecutive_errors 0
      log_detail "Switched to model index $MODEL_INDEX: ${MODELS[$MODEL_INDEX]}"
    fi
    sleep $SLEEP_ERROR
    continue
  fi
  
  set_state consecutive_errors 0
  log "Iteration completed successfully"
  log "Sleeping $SLEEP_NORMAL seconds before next iteration..."
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  sleep $SLEEP_NORMAL
done
