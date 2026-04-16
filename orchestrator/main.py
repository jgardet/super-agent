"""
Super-Agent Orchestrator
FastAPI + CrewAI — intent-routes tasks to specialist crews.
Active model is read from env; ./scripts/switch-model.sh restarts this service.
"""

import os
import importlib
import importlib.util
import string
from pathlib import Path
from typing import Optional, Any

import httpx
import yaml
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
def _expand_env(obj: Any) -> Any:
    """Recursively expand ${VAR} references in a loaded YAML structure."""
    if isinstance(obj, str):
        return string.Template(obj).safe_substitute(os.environ)
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    return obj

def _init_memory():
    if not (MEM0_AVAILABLE and MEM0_CONFIG_PATH.exists()):
        return None
    try:
        with open(MEM0_CONFIG_PATH) as f:
            raw = yaml.safe_load(f)
        cfg = _expand_env(raw)
        # Ensure history dir exists (mem0 won't create parents)
        hist = cfg.get("history_db_path")
        if hist:
            Path(hist).parent.mkdir(parents=True, exist_ok=True)
        return Memory.from_config(cfg)
    except Exception as e:
        print(f"Warning: Failed to initialize Mem0: {e}")
        return None

memory = _init_memory()

DEFAULT_USER_ID = os.getenv("MEMORY_DEFAULT_USER", "super-agent")

def mem_add(task: str, result: str, crew: str, user_id: str) -> None:
    """Store a task/result pair in Mem0 with proper signature."""
    if not memory:
        return
    try:
        memory.add(
            [
                {"role": "user", "content": task},
                {"role": "assistant", "content": result},
            ],
            user_id=user_id,
            metadata={"crew": crew, "mode": MODEL_MODE, "model": ACTIVE_MODEL},
        )
    except Exception as e:
        print(f"Warning: memory.add failed: {e}")

def mem_recall(query: str, user_id: str, limit: int = 5) -> list:
    """Fetch relevant past memories to enrich a new task."""
    if not memory:
        return []
    try:
        res = memory.search(query, user_id=user_id, limit=limit)
        # Mem0 returns dict with 'results' or raw list depending on version
        if isinstance(res, dict):
            return res.get("results", []) or []
        return res or []
    except Exception as e:
        print(f"Warning: memory.search failed: {e}")
        return []

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
# Fallback keyword-based classification
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

def classify_task_fallback(prompt: str) -> str:
    """Fallback keyword-based classification."""
    prompt_lower = prompt.lower()
    scores = {crew: sum(1 for kw in kws if kw in prompt_lower)
              for crew, kws in TASK_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "research"

def classify_task(prompt: str) -> str:
    """
    Classify task intent using LLM for semantic understanding.
    Falls back to keyword matching if LLM fails.
    """
    llm = get_llm()

    system_prompt = """You are an intent classifier for a multi-agent AI system.
Classify the user's task into one of these categories:
- coding: Writing, debugging, refactoring, or testing code
- research: Finding information, comparing options, explaining concepts
- ops: Deployment, automation, scheduling, file organization
- analysis: Data analysis, reporting, metrics, dashboards

Respond with ONLY the category name (lowercase)."""

    try:
        # OllamaLLM is a completion model; pass a single prompt string.
        result = llm.invoke(f"{system_prompt}\n\nTask: {prompt}\n\nCategory:")

        # Extract the category from LLM response
        category = result.strip().lower().split()[0].strip(".,:")
        valid_categories = {"coding", "research", "ops", "analysis"}

        if category in valid_categories:
            return category
        else:
            # LLM returned invalid category, use fallback
            print(f"Warning: LLM returned invalid category '{category}', using fallback")
            return classify_task_fallback(prompt)

    except Exception as e:
        print(f"Warning: LLM classification failed: {e}, using fallback")
        return classify_task_fallback(prompt)

# ── Crew runner ─────────────────────────────────────────────────────────────────
def _format_memories(mems: list) -> str:
    if not mems:
        return ""
    lines = []
    for m in mems[:5]:
        if isinstance(m, dict):
            txt = m.get("memory") or m.get("text") or m.get("content") or str(m)
        else:
            txt = str(m)
        lines.append(f"- {txt}")
    return "Relevant past context:\n" + "\n".join(lines)

def run_crew(crew_name: str, task: str, context: dict, llm, user_id: str) -> str:
    """Dynamically loads crews/{crew_name}.py and calls run(task, llm, context).

    Enriches context with prior memories and persists results.
    """
    # Inject recalled memories into context so crews benefit from cross-session state.
    recalled = mem_recall(task, user_id=user_id, limit=5)
    enriched_context = dict(context or {})
    if recalled:
        enriched_context["memories"] = recalled
        enriched_context.setdefault("memory_summary", _format_memories(recalled))

    crew_path = CREWS_DIR / f"{crew_name}.py"
    if not crew_path.exists():
        # Graceful fallback: direct LLM call
        prompt = task
        if recalled:
            prompt = f"{_format_memories(recalled)}\n\nTask: {task}\n\nContext: {enriched_context}"
        result = llm.invoke(prompt)
        mem_add(task, str(result), crew_name, user_id)
        return str(result)

    spec = importlib.util.spec_from_file_location(crew_name, crew_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(task=task, llm=llm, context=enriched_context)
    mem_add(task, str(result), crew_name, user_id)
    return str(result)

# ── Schemas ────────────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    prompt: str
    crew: Optional[str] = None       # force crew; omit for auto-routing
    context: Optional[dict] = {}
    use_reasoning_llm: bool = False  # set True to route to Claude (needs API key)
    user_id: Optional[str] = None    # namespace for memory; defaults to DEFAULT_USER_ID

class MemoryAddRequest(BaseModel):
    content: str
    user_id: Optional[str] = None
    source: Optional[str] = "external"   # e.g. 'openclaw', 'n8n'
    metadata: Optional[dict] = None

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
    user_id = req.user_id or DEFAULT_USER_ID
    model_label = ACTIVE_MODEL

    # Actually wire the reasoning LLM through to the crew when requested.
    if req.use_reasoning_llm and ANTHROPIC_KEY:
        llm = get_reasoning_llm()
        model_label = "claude-sonnet-4-6"
    else:
        llm = get_llm()

    try:
        result = run_crew(crew_name, req.prompt, req.context or {}, llm=llm, user_id=user_id)
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
def search_memory(query: str, limit: int = 5, user_id: Optional[str] = None):
    """Search Mem0 vector store for relevant past context."""
    if not memory:
        return {"error": "Memory not available", "query": query}
    uid = user_id or DEFAULT_USER_ID
    try:
        results = memory.search(query, user_id=uid, limit=limit)
        if isinstance(results, dict):
            results = results.get("results", [])
        return {
            "status": "memory_available",
            "query": query,
            "user_id": uid,
            "results": results,
            "count": len(results) if results else 0,
        }
    except Exception as exc:
        return {"error": str(exc), "query": query}

@app.post("/memory", tags=["memory"])
def add_memory(req: MemoryAddRequest):
    """Shared write endpoint so OpenClaw/n8n/other agents can contribute memory."""
    if not memory:
        raise HTTPException(status_code=503, detail="Memory not available")
    uid = req.user_id or DEFAULT_USER_ID
    meta = dict(req.metadata or {})
    meta.setdefault("source", req.source or "external")
    try:
        memory.add(req.content, user_id=uid, metadata=meta)
        return {"status": "stored", "user_id": uid, "source": meta["source"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.delete("/memory", tags=["memory"])
def reset_memory(user_id: Optional[str] = None):
    """Clear memory for a user (defaults to the shared user)."""
    if not memory:
        raise HTTPException(status_code=503, detail="Memory not available")
    uid = user_id or DEFAULT_USER_ID
    try:
        memory.delete_all(user_id=uid)
        return {"status": "cleared", "user_id": uid}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
