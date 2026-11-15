#!/bin/bash

# Autonomous Agent Runner for OpenCode
# Runs tasks continuously with sleep intervals and model switching on rate limits

WORKDIR="/media/saksham/phone data/programming_projects/upsc_app"
LOG_DIR="$WORKDIR/logs"
mkdir -p "$LOG_DIR"

# Models to try in order (fallback chain)
MODELS=(
  "opencode-go/iceman-contributor-free"
  "opencode-go/glm-5.3-flash"
  "opencode-go/deepseek-v4.1-flash"
  "opencode-go/qwen3.8-flash"
  "opencode-go/kimi-k2.7-code"
  "opencode-go/gemini-4-argon"
  "opencode-go/mimo-v2.6-flash"
)

# Configuration
SLEEP_BETWEEN_RUNS=300  # 5 minutes between runs
SLEEP_ON_RATE_LIMIT=600 # 10 minutes on rate limit
MAX_RETRIES=3
TASK_PROMPT="Continue executing the UPSC CSE 2027 knowledge base task from /media/saksham/phone data/programming_projects/upsc_app/notes/upsc_notes_task.md. Follow the workflow systematically, work on the next incomplete phase, save progress incrementally. Focus on building comprehensive notes for all subjects."

MODEL_INDEX=0
ITERATION=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/auto_runner.log"
}

while true; do
  ITERATION=$((ITERATION + 1))
  CURRENT_MODEL="${MODELS[$MODEL_INDEX]}"
  LOG_FILE="$LOG_DIR/run_${ITERATION}_$(date +%Y%m%d_%H%M%S).log"
  
  log "=== Iteration $ITERATION starting with model: $CURRENT_MODEL ==="
  log "Working directory: $WORKDIR"
  
  cd "$WORKDIR" || exit 1
  
  # Run opencode with the task
  timeout 3600 opencode run -m "$CURRENT_MODEL" --auto "$TASK_PROMPT" 2>&1 | tee "$LOG_FILE"
  
  EXIT_CODE=${PIPESTATUS[0]}
  log "Run completed with exit code: $EXIT_CODE"
  
  # Check for rate limit errors
  if grep -qi "rate limit\|quota\|too many requests\|429\|limit exceeded" "$LOG_FILE"; then
    log "Rate limit detected. Switching model and sleeping longer..."
    MODEL_INDEX=$(( (MODEL_INDEX + 1) % ${#MODELS[@]} ))
    log "Switched to model: ${MODELS[$MODEL_INDEX]}"
    sleep $SLEEP_ON_RATE_LIMIT
    continue
  fi
  
  # Check for authentication errors
  if grep -qi "unauthorized\|auth\|api key\|401" "$LOG_FILE"; then
    log "Auth error detected. Sleeping before retry..."
    sleep $SLEEP_ON_RATE_LIMIT
    continue
  fi
  
  # If successful or completed, sleep normally and continue
  if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 124 ]; then  # 124 is timeout
    log "Iteration completed. Sleeping for $SLEEP_BETWEEN_RUNS seconds..."
    sleep $SLEEP_BETWEEN_RUNS
  else
    log "Error occurred. Retrying after shorter sleep..."
    sleep 120
  fi
  
  # Optional: limit iterations if needed
  # if [ $ITERATION -ge 100 ]; then break; fi
done
