"""
Super-Agent Orchestrator
FastAPI + CrewAI — intent-routes tasks to specialist crews.
Active model is read from env; ./scripts/switch-model.sh restarts this service.
"""

import os
import importlib
import importlib.util
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_ollama import OllamaLLM

# Mem0 for cross-session memory
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

# Optional: Claude as reasoning fallback
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if ANTHROPIC_KEY:
    from langchain_anthropic import ChatAnthropic

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
ACTIVE_MODEL    = os.getenv("ACTIVE_MODEL", "glm-5.1:cloud")
MODEL_MODE      = os.getenv("MODEL_MODE", "cloud")
QDRANT_HOST     = os.getenv("QDRANT_HOST", "http://qdrant:6333")
CREWS_DIR       = Path("/app/crews")
MEM0_CONFIG_PATH = Path("/app/mem0-config.yaml")

# ── Mem0 Memory ─────────────────────────────────────────────────────────────────
memory = None
if MEM0_AVAILABLE and MEM0_CONFIG_PATH.exists():
    try:
        memory = Memory.from_config_file(str(MEM0_CONFIG_PATH))
    except Exception as e:
        print(f"Warning: Failed to initialize Mem0: {e}")
        memory = None

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Super-Agent Orchestrator",
    description="CrewAI multi-agent REST API with intent routing and model switching.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── LLM factory ────────────────────────────────────────────────────────────────
def get_llm(temperature: float = 0.1) -> OllamaLLM:
    return OllamaLLM(
        model=ACTIVE_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )

def get_reasoning_llm():
    """Uses Claude if API key present; falls back to Ollama."""
    if ANTHROPIC_KEY:
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            anthropic_api_key=ANTHROPIC_KEY,
            temperature=0.1,
        )
    return get_llm()

# ── Intent router ───────────────────────────────────────────────────────────────
TASK_KEYWORDS = {
    "coding":   ["code", "bug", "function", "script", "refactor", "debug",
                 "test", "implement", "python", "javascript", "typescript", "api"],
    "research": ["research", "find", "search", "summarize", "compare",
                 "explain", "analyse", "analyze", "what is", "how does"],
    "ops":      ["deploy", "monitor", "schedule", "cron", "email", "calendar",
                 "file", "organize", "automate", "workflow"],
    "analysis": ["analyse", "analyze", "data", "report", "chart", "metrics",
                 "kpi", "dashboard", "trend"],
}

def classify_task(prompt: str) -> str:
    prompt_lower = prompt.lower()
    scores = {crew: sum(1 for kw in kws if kw in prompt_lower)
              for crew, kws in TASK_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "research"

# ── Crew runner ─────────────────────────────────────────────────────────────────
def run_crew(crew_name: str, task: str, context: dict) -> str:
    """Dynamically loads crews/{crew_name}.py and calls run(task, llm, context)."""
    crew_path = CREWS_DIR / f"{crew_name}.py"
    if not crew_path.exists():
        # Graceful fallback: direct LLM call
        llm = get_llm()
        result = llm.invoke(f"{task}\n\nContext: {context}")
        # Store in memory if available
        if memory:
            try:
                memory.add(task, result, metadata={"crew": crew_name, "mode": MODEL_MODE})
            except Exception:
                pass
        return result

    spec = importlib.util.spec_from_file_location(crew_name, crew_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(task=task, llm=get_llm(), context=context)
    # Store in memory if available
    if memory:
        try:
            memory.add(task, result, metadata={"crew": crew_name, "mode": MODEL_MODE})
        except Exception:
            pass
    return result

# ── Schemas ────────────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    prompt: str
    crew: Optional[str] = None       # force crew; omit for auto-routing
    context: Optional[dict] = {}
    use_reasoning_llm: bool = False  # set True to route to Claude (needs API key)

class TaskResponse(BaseModel):
    result: str
    crew_used: str
    model_used: str
    mode: str

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "model": ACTIVE_MODEL, "mode": MODEL_MODE}

@app.get("/status", tags=["system"])
def status():
    return {
        "active_model": ACTIVE_MODEL,
        "model_mode": MODEL_MODE,
        "ollama_url": OLLAMA_BASE_URL,
        "qdrant_url": QDRANT_HOST,
        "anthropic_available": bool(ANTHROPIC_KEY),
        "memory_available": memory is not None,
        "crews_available": sorted(p.stem for p in CREWS_DIR.glob("*.py")
                                  if not p.stem.startswith("_")),
    }

@app.post("/run", response_model=TaskResponse, tags=["agent"])
def run_task(req: TaskRequest):
    crew_name = req.crew or classify_task(req.prompt)
    model_label = ACTIVE_MODEL

    if req.use_reasoning_llm and ANTHROPIC_KEY:
        model_label = "claude-sonnet-4-6"

    try:
        result = run_crew(crew_name, req.prompt, req.context or {})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return TaskResponse(
        result=result,
        crew_used=crew_name,
        model_used=model_label,
        mode=MODEL_MODE,
    )

@app.get("/models", tags=["system"])
def list_models():
    """List models currently available in Ollama."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.json()
    except Exception as exc:
        return {"error": str(exc), "ollama_url": OLLAMA_BASE_URL}

@app.get("/memory/search", tags=["memory"])
def search_memory(query: str, limit: int = 5):
    """Search Mem0 vector store for relevant past context."""
    if not memory:
        return {"error": "Memory not available", "query": query}
    try:
        results = memory.search(query, limit=limit)
        return {
            "status": "memory_available",
            "query": query,
            "results": results,
            "count": len(results) if results else 0
        }
    except Exception as exc:
        return {"error": str(exc), "query": query}
