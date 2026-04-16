#!/bin/sh
# Runs once at stack start — pulls local model if MODEL_MODE=local
# In cloud mode, just validates Ollama is reachable (cloud models need no pull)

echo "=== Ollama init ==="
echo "  MODEL_MODE : ${MODEL_MODE:-cloud}"
echo "  OLLAMA_HOST: ${OLLAMA_HOST:-http://ollama:11434}"

if [ "${MODEL_MODE:-cloud}" = "local" ]; then
  echo "  Pulling local model: $LOCAL_MODEL"
  curl -sf -X POST "$OLLAMA_HOST/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$LOCAL_MODEL\"}" \
    | grep -E '"status"' | tail -3
  echo "  Done: $LOCAL_MODEL"

  # Pull embedding model (lightweight, needed for Mem0/Qdrant memory)
  echo "  Pulling embedding model: nomic-embed-text"
  curl -sf -X POST "$OLLAMA_HOST/api/pull" \
    -H "Content-Type: application/json" \
    -d '{"name": "nomic-embed-text"}' \
    | grep -E '"status"' | tail -2
  echo "  Done: nomic-embed-text"
else
  # Cloud mode: just verify connectivity
  echo "  Cloud mode — no local pull needed."
  echo "  Verifying Ollama is reachable..."
  curl -sf "$OLLAMA_HOST/api/tags" > /dev/null \
    && echo "  Ollama OK." \
    || echo "  Warning: Ollama not reachable yet — services will retry."
fi
