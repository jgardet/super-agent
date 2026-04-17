#!/bin/sh
# Bootstrap sa-openclaw on first boot.
#
# Installs CLIs (openclaw, opencode), writes an openclaw.json that declares
# Ollama as a model provider (equivalent to running `ollama launch openclaw`
# interactively, but works without a TTY), and registers a `coder` agent.
# State is persisted via the `openclaw_state` volume so the seed step only
# runs once per volume.
set -eu

CONFIG_FILE="/root/.openclaw/openclaw.json"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
OLLAMA_MODEL_TAG="${OPENCLAW_BOOTSTRAP_MODEL:-minimax-m2:cloud}"

log() { echo "[bootstrap] $*"; }

log "installing apt deps…"
apt-get update -qq
apt-get install -y --no-install-recommends \
    git ca-certificates python3 procps curl >/dev/null

log "installing openclaw + opencode via npm…"
npm install -g openclaw@latest opencode-ai@latest 2>&1 | tail -5

mkdir -p /root/.openclaw

if [ ! -s "$CONFIG_FILE" ] || ! grep -q '"ollama"' "$CONFIG_FILE" 2>/dev/null; then
    log "first boot — writing openclaw.json with Ollama as model provider"
    python3 - <<PY
import json, pathlib, secrets
p = pathlib.Path("$CONFIG_FILE")
existing = {}
if p.exists() and p.read_text().strip():
    try:
        existing = json.loads(p.read_text())
    except Exception:
        existing = {}

token = existing.get("gateway", {}).get("auth", {}).get("token") or secrets.token_hex(24)

cfg = {
    "gateway": {
        "auth": {"mode": "token", "token": token},
        "mode": "local",
        "port": 18789,
        "bind": "loopback",
        "controlUi": {
            "allowedOrigins": [
                "http://localhost:18789",
                "http://127.0.0.1:18789",
            ]
        },
    },
    "models": {
        "mode": "merge",
        "providers": {
            "ollama": {
                "api": "ollama",
                "baseUrl": "$OLLAMA_BASE_URL",
                "models": [
                    {"id": "minimax-m2:cloud",       "name": "minimax-m2:cloud",       "reasoning": False, "input": ["text"], "contextWindow": 204800, "maxTokens": 8192},
                    {"id": "glm-5.1:cloud",          "name": "glm-5.1:cloud",          "reasoning": False, "input": ["text"], "contextWindow": 202752, "maxTokens": 8192},
                    {"id": "qwen3.5:9b",             "name": "qwen3.5:9b",             "reasoning": False, "input": ["text", "image"], "contextWindow": 262144, "maxTokens": 8192},
                    {"id": "nomic-embed-text:latest","name": "nomic-embed-text:latest","reasoning": False, "input": ["text"], "contextWindow": 2048,   "maxTokens": 8192},
                ],
            }
        },
    },
    "plugins": {"entries": {"ollama": {"enabled": True}}},
    "agents": {
        "defaults": {
            "model": {"primary": "ollama/$OLLAMA_MODEL_TAG"},
            "workspace": "/root/.openclaw/workspace",
        },
        "list": existing.get("agents", {}).get("list", [{"id": "main"}]),
    },
    "tools": {"profile": "coding"},
    "session": {"dmScope": "per-channel-peer"},
    "meta": {"lastTouchedVersion": "2026.4.15", "lastTouchedAt": "bootstrap"},
}
p.write_text(json.dumps(cfg, indent=2))
print("  wrote", p, "with primary model ollama/$OLLAMA_MODEL_TAG")
PY

    log "validating config"
    openclaw config validate 2>&1 | tail -3 || true

    if ! openclaw agents list 2>/dev/null | grep -q '^- coder'; then
        log "registering coder agent (workspace=/root/.openclaw/agents/coder/workspace)"
        # Agent's own workspace is its scaffolding dir, NOT /workspace.
        # The coding-agent skill calls `opencode run` with workdir:/workspace
        # explicitly so file ops happen in the shared volume.
        openclaw agents add coder \
            --workspace /root/.openclaw/agents/coder/workspace \
            --model "ollama/$OLLAMA_MODEL_TAG" \
            --non-interactive --json 2>&1 | tail -10 || true
    else
        log "coder agent already registered"
    fi
else
    log "config already present ($CONFIG_FILE) — skipping first-boot seed"
fi

if ! command -v openclaw >/dev/null 2>&1 || ! command -v opencode >/dev/null 2>&1; then
    log "✗ CLI tools missing after install — container idle so you can inspect"
    log "  debug: docker exec -it sa-openclaw sh"
    exec tail -f /dev/null
fi

log "✓ starting gateway on :18789"
exec openclaw gateway --port 18789 --allow-unconfigured
