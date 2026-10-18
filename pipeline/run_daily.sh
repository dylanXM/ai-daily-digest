#!/bin/bash
# ai-daily daily pipeline (one-click)
#   compute "yesterday" -> run collect.py -> run build.py -> git push (if configured)
set -euo pipefail

AI_DAILY="$HOME/workspace/ai-daily"
YESTERDAY="$(TZ=America/New_York date -d "yesterday" +%F)"
LOG_DIR="$AI_DAILY/logs"
LOG_FILE="$LOG_DIR/${YESTERDAY}.log"
mkdir -p "$LOG_DIR"

{
  echo "=================================================================="
  echo "[$(date '+%F %T %Z')] ai-daily daily pipeline started, target date: $YESTERDAY"
  echo "=================================================================="

  echo "--- [1/4] collecting content ---"
  python3 "$AI_DAILY/pipeline/collect.py" "$YESTERDAY"
  echo "collection done, exit code: $?"

  echo "--- [2/4] rebuilding site ---"
  if [ -f "$AI_DAILY/build.py" ]; then
    python3 "$AI_DAILY/build.py"
    echo "site rebuilt"
  else
    echo "[warn] $AI_DAILY/build.py not found, skipping site build (data files are ready)"
  fi

  echo "--- [3/4] rendering newsletter HTML (non-fatal) ---"
  mkdir -p "$AI_DAILY/newsletters"
  if python3 "$AI_DAILY/beehiiv_draft.py" --render-only --date "$YESTERDAY" --out "$AI_DAILY/newsletters/${YESTERDAY}.html"; then
    echo "newsletter HTML ready: newsletters/${YESTERDAY}.html"
  else
    echo "[warn] newsletter render failed, continuing"
  fi

  echo "--- [4/4] pushing to GitHub ---"
  if [ -f "$AI_DAILY/.github-sync" ]; then
    cd "$AI_DAILY"
    export GIT_SSH_COMMAND="ssh -F /home/hatch/.ssh/config"
    git add -A
    if git diff --cached --quiet; then
      echo "nothing new to push"
    else
      git commit -qm "daily update: $YESTERDAY" && git push origin main
      echo "pushed to GitHub"
    fi
  else
    echo "[skip] $AI_DAILY/.github-sync not found, GitHub sync not configured"
  fi

  echo "[$(date '+%F %T %Z')] ai-daily daily pipeline finished"
} 2>&1 | tee "$LOG_FILE"

echo "log written to: $LOG_FILE"
