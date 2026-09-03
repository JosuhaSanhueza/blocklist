#!/bin/bash
# Corre una tanda diaria de búsqueda con Claude Code en modo no interactivo.
# Pensado para invocarse desde cron, sin supervisión humana.
set -euo pipefail

# cron corre con un PATH mínimo y no lee .bashrc — agregamos explícitamente
# dónde quedó instalado el CLI (npm con prefix de usuario, sin sudo).
export PATH="$HOME/.npm-global/bin:$PATH"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/scripts/logs"
LOG_FILE="$LOG_DIR/daily_search_$(date +%Y-%m-%d_%H%M).log"
ENV_FILE="$REPO_DIR/scripts/.env.local"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

{
  echo "=== Corrida diaria: $(date) ==="

  # Token de larga duración para uso desatendido (CLAUDE_CODE_OAUTH_TOKEN),
  # guardado localmente fuera de git — nunca se commitea.
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    echo "[ERROR] CLAUDE_CODE_OAUTH_TOKEN no está seteado."
    echo "  Creá $ENV_FILE con la línea:"
    echo '  export CLAUDE_CODE_OAUTH_TOKEN="tu-token-aca"'
    exit 1
  fi

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
