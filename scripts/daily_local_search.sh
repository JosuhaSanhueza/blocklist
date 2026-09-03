#!/bin/bash
# Corre una tanda diaria de búsqueda con Claude Code en modo no interactivo.
# Pensado para invocarse desde cron, sin supervisión humana.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/scripts/logs"
LOG_FILE="$LOG_DIR/daily_search_$(date +%Y-%m-%d_%H%M).log"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

{
  echo "=== Corrida diaria: $(date) ==="

  if ! command -v claude >/dev/null 2>&1; then
    echo "[ERROR] El comando 'claude' no está en el PATH. Instalalo con:"
    echo "  npm install -g @anthropic-ai/claude-code"
    exit 1
  fi

  claude --dangerously-skip-permissions -p "$(cat scripts/daily_search_prompt.md)"

  echo "=== Fin: $(date) ==="
} >> "$LOG_FILE" 2>&1

# Conservar solo los últimos 30 logs
find "$LOG_DIR" -name "daily_search_*.log" -type f -mtime +30 -delete
