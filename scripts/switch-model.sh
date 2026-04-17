#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# switch-model.sh  —  toggle between Ollama-cloud and local GPU inference
#
# Usage:
#   ./scripts/switch-model.sh                     → show current config
#   ./scripts/switch-model.sh cloud               → minimax-m2.7:cloud (default)
#   ./scripts/switch-model.sh local               → LOCAL_MODEL from .env
#   ./scripts/switch-model.sh local qwen3.5:9b    → local with override model
# ─────────────────────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

MODE="${1:-}"
OVERRIDE_MODEL="${2:-}"

# ── No argument: show status ──────────────────────────────────────────────────
if [ -z "$MODE" ]; then
  echo -e "${CYAN}${BOLD}Super-Agent · Current Config${NC}"
  echo "─────────────────────────────────"
  if [ -f "$ENV_FILE" ]; then
    grep -E '^(MODEL_MODE|ACTIVE_MODEL|LOCAL_MODEL)=' "$ENV_FILE" | \
      sed 's/^/  /'
  else
    echo -e "  ${YELLOW}.env not found — run: cp .env.example .env${NC}"
  fi
  echo ""
  echo "Usage: $0 cloud|local [model-override]"
  exit 0
fi

echo -e "${CYAN}${BOLD}Super-Agent · Model Switch${NC}"
echo "─────────────────────────────────"

# ── Cloud mode ────────────────────────────────────────────────────────────────
if [ "$MODE" = "cloud" ]; then
  ACTIVE_MODEL="${OVERRIDE_MODEL:-minimax-m2.7:cloud}"
  echo -e "  Mode:  ${GREEN}cloud${NC}"
  echo -e "  Model: ${GREEN}$ACTIVE_MODEL${NC}"
  echo -e "  VRAM:  ${GREEN}0 GB${NC} (proxied via Ollama cloud)"

# ── Local mode ────────────────────────────────────────────────────────────────
elif [ "$MODE" = "local" ]; then
  if [ -n "$OVERRIDE_MODEL" ]; then
    LOCAL_MODEL="$OVERRIDE_MODEL"
  else
    LOCAL_MODEL=$(grep '^LOCAL_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "glm-4.7-flash")
    LOCAL_MODEL="${LOCAL_MODEL:-glm-4.7-flash}"
  fi
  ACTIVE_MODEL="$LOCAL_MODEL"
  echo -e "  Mode:  ${YELLOW}local${NC} (uses your GPU)"
  echo -e "  Model: ${YELLOW}$LOCAL_MODEL${NC}"

  # Approximate VRAM guidance — verify against your own GPU before pulling
  case "$LOCAL_MODEL" in
    glm-4.7-flash)          echo -e "  VRAM:  ${GREEN}~8 GB  (MoE 30B / 3B active)${NC}" ;;
    qwen3-coder:14b)        echo -e "  VRAM:  ${GREEN}~9 GB  (14B dense)${NC}" ;;
    qwen3.5:9b)             echo -e "  VRAM:  ${GREEN}~6 GB  (9B dense)${NC}" ;;
    qwen3.5:27b)            echo -e "  VRAM:  ${YELLOW}~17 GB (27B dense) — needs a large GPU${NC}" ;;
    glm-5.1|glm-5.1:latest) echo -e "  VRAM:  ${RED}~400+ GB (754B MoE) — not runnable locally${NC}"; exit 1 ;;
    *)                      echo -e "  VRAM:  ${YELLOW}unknown — check ollama.com/library/$LOCAL_MODEL${NC}" ;;
  esac

  # Pull model if not already present
  echo ""
  echo -n "  Checking if $LOCAL_MODEL is in Ollama... "
  if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T ollama \
       ollama list 2>/dev/null | grep -q "$LOCAL_MODEL"; then
    echo -e "${GREEN}already present${NC}"
  else
    echo -e "${YELLOW}pulling...${NC}"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" exec ollama \
      ollama pull "$LOCAL_MODEL"
  fi

  # Also pull embedding model if missing (used by Mem0)
  echo -n "  Checking nomic-embed-text... "
  if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T ollama \
       ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
    echo -e "${GREEN}already present${NC}"
  else
    echo -e "${YELLOW}pulling...${NC}"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" exec ollama \
      ollama pull nomic-embed-text
  fi

else
  echo -e "${RED}Unknown mode '$MODE'. Use 'cloud' or 'local'.${NC}"
  exit 1
fi

# ── Update .env ───────────────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
  sed -i "s/^MODEL_MODE=.*/MODEL_MODE=$MODE/" "$ENV_FILE"
  if grep -q '^ACTIVE_MODEL=' "$ENV_FILE"; then
    sed -i "s|^ACTIVE_MODEL=.*|ACTIVE_MODEL=$ACTIVE_MODEL|" "$ENV_FILE"
  else
    echo "ACTIVE_MODEL=$ACTIVE_MODEL" >> "$ENV_FILE"
  fi
  if [ "$MODE" = "local" ] && grep -q '^LOCAL_MODEL=' "$ENV_FILE"; then
    sed -i "s|^LOCAL_MODEL=.*|LOCAL_MODEL=$LOCAL_MODEL|" "$ENV_FILE"
  fi
  echo ""
  echo -e "  ${GREEN}✓ .env updated${NC}  MODEL_MODE=$MODE  ACTIVE_MODEL=$ACTIVE_MODEL"
else
  echo -e "\n  ${YELLOW}Warning: .env not found. Copy .env.example to .env first.${NC}"
fi

# Also update opencode-config.json model field
OPENCODE_CFG="$PROJECT_DIR/config/opencode-config.json"
if [ -f "$OPENCODE_CFG" ]; then
  # Use python for reliable JSON editing
  python3 -c "
import json, sys
with open('$OPENCODE_CFG') as f: cfg = json.load(f)
cfg['model'] = '$ACTIVE_MODEL'
with open('$OPENCODE_CFG', 'w') as f: json.dump(cfg, f, indent=2)
print('  ✓ opencode-config.json updated')
" 2>/dev/null || true
fi

# ── Restart affected services ─────────────────────────────────────────────────
echo ""
echo "  Restarting services..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" \
  up -d --no-deps opencode openclaw orchestrator

echo ""
echo -e "${GREEN}${BOLD}Done.${NC}"
echo "  Active model: ${CYAN}$ACTIVE_MODEL${NC}  (mode: $MODE)"
echo ""
echo "  Services:"
echo "    Open-WebUI:   http://localhost:3000"
echo "    Orchestrator: http://localhost:8000/docs"
echo "    n8n:          http://localhost:5678"
echo "    Ollama API:   http://localhost:11434/api/tags"
