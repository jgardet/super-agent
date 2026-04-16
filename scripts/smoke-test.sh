#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# smoke-test.sh — verify all services are healthy after docker compose up -d
# Usage: ./scripts/smoke-test.sh
# ─────────────────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS=0; FAIL=0

check() {
  local name="$1" url="$2" expect="$3"
  local result
  result=$(curl -sf --max-time 5 "$url" 2>/dev/null)
  if echo "$result" | grep -q "$expect"; then
    echo -e "  ${GREEN}✓${NC} $name"
    PASS=$((PASS+1))
  else
    echo -e "  ${RED}✗${NC} $name  (${url})"
    FAIL=$((FAIL+1))
  fi
}

echo -e "${CYAN}${BOLD}Super-Agent · Smoke Test${NC}"
echo "─────────────────────────────────"

check "Ollama"        "http://localhost:11434/api/tags"  "models"
check "Orchestrator"  "http://localhost:8000/health"     "ok"
check "Qdrant"        "http://localhost:6333/readyz"     "ok"
check "Open-WebUI"    "http://localhost:3000"            "html"
check "n8n"          "http://localhost:5678"            "n8n"

echo ""
echo -e "Orchestrator status:"
curl -sf http://localhost:8000/status 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  [print(f'  {k}: {v}') for k,v in d.items()]" 2>/dev/null || \
  echo "  (orchestrator not yet ready)"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}All checks passed ($PASS/$((PASS+FAIL)))${NC}"
  echo ""
  echo "  Open-WebUI:   http://localhost:3000"
  echo "  Orchestrator: http://localhost:8000/docs"
  echo "  n8n:          http://localhost:5678  [admin / changeme]"
else
  echo -e "${YELLOW}$FAIL service(s) not ready yet.${NC} Wait 30s and retry, or:"
  echo "  docker compose ps"
  echo "  docker compose logs --tail=30 <service>"
fi
