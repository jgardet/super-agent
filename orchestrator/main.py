"""
Super-Agent Orchestrator  v2
FastAPI + CrewAI + Mem0 + async task queue + planner meta-crew.

Highlights:
  - Async job queue (ThreadPoolExecutor): POST /run returns job_id immediately;
    set `sync=true` to wait up to 120s for callers that need an inline answer.
  - Planner meta-crew: decomposes multi-step goals and recurses into other crews
    via the `orchestrator_bridge` injection.
  - Shared Mem0/Qdrant memory with per-user_id isolation, automatic recall into
    crew context, and a cross-agent /memory write endpoint.
  - Tavily web search plumbed through to the research crew when TAVILY_API_KEY
    is set (see crews/research.py).
"""

import os
import sys
import types
import time
import uuid
import importlib
import importlib.util
import string
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crewai import LLM

# Mem0 for cross-session memory
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

# Optional: Claude as reasoning fallback
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
ACTIVE_MODEL    = os.getenv("ACTIVE_MODEL", "minimax-m2.7:cloud")
MODEL_MODE      = os.getenv("MODEL_MODE", "cloud")
QDRANT_HOST     = os.getenv("QDRANT_HOST", "http://qdrant:6333")
TAVILY_KEY      = os.getenv("TAVILY_API_KEY", "")
CREWS_DIR       = Path("/app/crews")
MEM0_CONFIG_PATH = Path("/app/mem0-config.yaml")
MAX_WORKERS     = int(os.getenv("ORCHESTRATOR_WORKERS", "4"))
SYNC_TIMEOUT_S  = int(os.getenv("ORCHESTRATOR_SYNC_TIMEOUT", "120"))

# ── Job queue state ───────────────────────────────────────────────────────────
# In-memory only. Survives orchestrator lifetime; swap for Redis when multi-replica.
_jobs: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="crew")

# Thread-local context so a job's reasoning-LLM preference and user_id are
# visible to every recursive call made via the orchestrator_bridge.
_ctx = threading.local()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

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
def get_llm(temperature: float = 0.1):
    """Return CrewAI 1.14+ LLM pointed at Ollama's OpenAI-compatible endpoint.

    CrewAI 1.14 routes `ollama/*` through its native OpenAI provider, which
    ignores a custom `api_base` in some code paths. We instead use the
    `openai/` provider explicitly against Ollama's /v1 endpoint, which works
    reliably for both local and Ollama-Cloud (e.g. `*:cloud`) models.
    """
    return LLM(
        model=f"openai/{ACTIVE_MODEL}",
        api_base=f"{OLLAMA_BASE_URL.rstrip('/')}/v1",
        api_key="ollama",  # dummy; Ollama doesn't require auth
        temperature=temperature,
    )

def get_reasoning_llm():
    """Uses Claude if API key present; falls back to Ollama."""
    if ANTHROPIC_KEY:
        return LLM(
            model="anthropic/claude-sonnet-4-6",
            api_key=ANTHROPIC_KEY,
            temperature=0.1,
        )
    return get_llm()

def _current_llm():
    """LLM for the currently-executing job.

    Honours the per-thread `use_reasoning` flag set by `_execute_job` so that
    the planner's recursive crew calls inherit the same LLM choice without
    any parameter-passing through the bridge.
    """
    if getattr(_ctx, "use_reasoning", False) and ANTHROPIC_KEY:
        return get_reasoning_llm()
    return get_llm()

def _current_user_id() -> str:
    return getattr(_ctx, "user_id", None) or DEFAULT_USER_ID

# ── Intent router ────────────────────────────────────────────────────────────────
# Fallback keyword-based classification. Planner is first-class: multi-step
# goals with words like "plan", "roadmap", "end-to-end" route here and the
# planner crew then decomposes and dispatches to the specialists below.
TASK_KEYWORDS = {
    "planner":  ["plan", "roadmap", "strategy", "end-to-end", "end to end",
                 "multi-step", "first research then", "prepare a",
                 "put together", "goal"],
    "coding":   ["code", "bug", "function", "script", "refactor", "debug",
                 "test", "implement", "python", "javascript", "typescript", "api"],
    "research": ["research", "find", "search", "summarize", "compare",
                 "explain", "analyse", "analyze", "what is", "how does",
                 "latest", "current"],
    "ops":      ["deploy", "monitor", "schedule", "cron", "email", "calendar",
                 "file", "organize", "automate", "workflow", "pipeline",
                 "ci/cd", "dockerfile", "kubernetes", "helm"],
    "analysis": ["analyse", "analyze", "data", "report", "chart", "metrics",
                 "kpi", "dashboard", "trend", "forecast"],
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
- planner: Multi-step goals requiring decomposition, strategy, roadmaps, or end-to-end workflows
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
        valid_categories = {"planner", "coding", "research", "ops", "analysis"}

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

def _install_bridge() -> None:
    """Expose `run_crew_by_name` as the `orchestrator_bridge` module.

    Planner (and any future meta-crew) imports this at runtime to recurse
    into the orchestrator without a circular import at module-load time.
    Installed once per process.
    """
    if "orchestrator_bridge" in sys.modules:
        return
    bridge = types.ModuleType("orchestrator_bridge")
    bridge.run_crew_by_name = run_crew_by_name
    sys.modules["orchestrator_bridge"] = bridge

def run_crew_by_name(crew_name: str, task: str, context: dict) -> str:
    """Dynamically load /app/crews/{crew_name}.py and call run(task, llm, context).

    - LLM is chosen from thread-local context (supports reasoning-LLM override
      throughout recursive planner calls).
    - Memory is recalled before the call and dual-written after.
    - The `orchestrator_bridge` module is guaranteed to be importable so the
      planner crew can recurse into other crews.
    """
    _install_bridge()
    llm = _current_llm()
    user_id = _current_user_id()

    # Inject recalled memories so crews benefit from cross-session state.
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

# Backwards-compatible alias (older callers imported `run_crew`).
run_crew = run_crew_by_name

# ── Job execution (runs in thread pool) ───────────────────────────────────────
def _execute_job(job_id: str, crew_name: str, prompt: str,
                 context: dict, use_reasoning: bool, user_id: str) -> None:
    _ctx.use_reasoning = bool(use_reasoning and ANTHROPIC_KEY)
    _ctx.user_id = user_id
    _jobs[job_id]["status"] = "running"
    try:
        result = run_crew_by_name(crew_name, prompt, context)
        _jobs[job_id].update({
            "status": "done",
            "result": str(result),
            "finished_at": _now(),
        })
    except Exception as exc:
        _jobs[job_id].update({
            "status": "error",
            "error": str(exc),
            "finished_at": _now(),
        })
    finally:
        _ctx.use_reasoning = False
        _ctx.user_id = None

# ── Schemas ────────────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    prompt: str
    crew: Optional[str] = None       # force crew; omit for auto-routing (incl. planner)
    context: Optional[dict] = {}
    use_reasoning_llm: bool = False  # set True to route to Claude (needs API key)
    user_id: Optional[str] = None    # namespace for memory; defaults to DEFAULT_USER_ID
    sync: bool = False               # True: wait up to SYNC_TIMEOUT_S for result

class MemoryAddRequest(BaseModel):
    content: str
    user_id: Optional[str] = None
    source: Optional[str] = "external"   # e.g. 'openclaw', 'n8n'
    metadata: Optional[dict] = None

class JobStatus(BaseModel):
    job_id: str
    status: str                          # queued | running | done | error
    crew_used: str
    model_used: str
    mode: str
    created_at: str
    finished_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None

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
        "anthropic_reasoning": bool(ANTHROPIC_KEY),
        "tavily_search": bool(TAVILY_KEY),
        "memory_available": memory is not None,
        "crews_available": sorted(p.stem for p in CREWS_DIR.glob("*.py")
                                  if not p.stem.startswith("_")),
        "workers": MAX_WORKERS,
        "jobs_in_memory": len(_jobs),
    }

def _job_to_status(job_id: str, job: dict) -> JobStatus:
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        crew_used=job["crew"],
        model_used=job["model_used"],
        mode=MODEL_MODE,
        created_at=job["created_at"],
        finished_at=job.get("finished_at"),
        result=job.get("result"),
        error=job.get("error"),
    )

@app.post("/run", response_model=JobStatus, tags=["agent"])
def run_task(req: TaskRequest):
    """Submit a task. Returns a job_id immediately.

    - `sync=false` (default): poll `GET /jobs/{job_id}` for the result.
    - `sync=true`: block up to `ORCHESTRATOR_SYNC_TIMEOUT` seconds (default 120)
      so OpenClaw / n8n / webhook callers can use it as a normal RPC.
    """
    crew_name = req.crew or classify_task(req.prompt)
    user_id = req.user_id or DEFAULT_USER_ID
    use_reasoning = bool(req.use_reasoning_llm and ANTHROPIC_KEY)
    model_label = "claude-sonnet-4-6" if use_reasoning else ACTIVE_MODEL
    job_id = str(uuid.uuid4())

    _jobs[job_id] = {
        "status": "queued",
        "crew": crew_name,
        "prompt": req.prompt,
        "model_used": model_label,
        "user_id": user_id,
        "result": None,
        "error": None,
        "created_at": _now(),
        "finished_at": None,
    }

    _executor.submit(
        _execute_job,
        job_id, crew_name, req.prompt, req.context or {},
        use_reasoning, user_id,
    )

    if req.sync:
        deadline = time.time() + SYNC_TIMEOUT_S
        while time.time() < deadline:
            if _jobs[job_id]["status"] in ("done", "error"):
                break
            time.sleep(0.25)

    return _job_to_status(job_id, _jobs[job_id])

@app.get("/jobs/{job_id}", response_model=JobStatus, tags=["jobs"])
def get_job(job_id: str):
    """Poll a job for its status and (when ready) result."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_status(job_id, _jobs[job_id])

@app.get("/jobs", tags=["jobs"])
def list_jobs(limit: int = 20):
    """List most recent jobs (newest first, capped at `limit`)."""
    sorted_jobs = sorted(
        _jobs.items(),
        key=lambda kv: kv[1]["created_at"],
        reverse=True,
    )[:limit]
    return [
        {
            "job_id": jid,
            "status": j["status"],
            "crew": j["crew"],
            "user_id": j.get("user_id"),
            "created_at": j["created_at"],
            "finished_at": j.get("finished_at"),
        }
        for jid, j in sorted_jobs
    ]

@app.delete("/jobs/{job_id}", tags=["jobs"])
def delete_job(job_id: str):
    """Remove a finished job from memory."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del _jobs[job_id]
    return {"deleted": job_id}

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

# ── OpenAI-compatible API (for Open-WebUI and other OpenAI clients) ───────────
# Exposes the orchestrator's crews as virtual "models". Open-WebUI can then be
# configured with this service as an additional OpenAI connection, letting the
# user pick between raw Ollama models and orchestrator-routed crews.

VIRTUAL_MODELS = {
    "orchestrator-auto":     "auto-route via classify_task (planner/research/coding/ops/analysis)",
    "orchestrator-planner":  "planner crew: decompose + delegate multi-step goals",
    "orchestrator-research": "research crew: find, compare, explain",
    "orchestrator-coding":   "coding crew: write/debug/refactor code",
    "orchestrator-ops":      "ops crew: deployment, automation, file ops",
    "orchestrator-analysis": "analysis crew: data analysis, metrics, reports",
}

@app.get("/v1/models", tags=["openai"])
def openai_list_models():
    """OpenAI-compatible model list. Exposed at /v1/models for Open-WebUI."""
    now = int(time.time())
    data = [
        {"id": mid, "object": "model", "created": now, "owned_by": "super-agent",
         "description": desc}
        for mid, desc in VIRTUAL_MODELS.items()
    ]
    return {"object": "list", "data": data}

class _OAIMessage(BaseModel):
    role: str
    content: Any  # string or list of content parts

class OpenAIChatRequest(BaseModel):
    model: str
    messages: list[_OAIMessage]
    stream: Optional[bool] = False
    user: Optional[str] = None
    # Extra fields tolerated and ignored (temperature, top_p, etc.)
    class Config:
        extra = "allow"

def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text") or p.get("content") or "")
            else:
                parts.append(str(p))
        return "\n".join(filter(None, parts))
    return str(content)

def _resolve_crew(model_id: str) -> Optional[str]:
    """Map virtual model name to a crew name, or None for auto-routing."""
    m = model_id.lower().strip()
    if m in ("orchestrator-auto", "auto"):
        return None
    if m.startswith("orchestrator-"):
        return m.split("-", 1)[1]
    return m  # allow bare "planner", "research", ...

@app.post("/v1/chat/completions", tags=["openai"])
def openai_chat_completions(req: OpenAIChatRequest):
    """OpenAI-compatible chat completions. Synchronous (non-streaming)."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    # Flatten prompt: system messages become prefix context, last user msg is task.
    system_parts = [_extract_text(m.content) for m in req.messages if m.role == "system"]
    user_parts   = [_extract_text(m.content) for m in req.messages if m.role == "user"]
    asst_parts   = [_extract_text(m.content) for m in req.messages if m.role == "assistant"]

    if not user_parts:
        raise HTTPException(status_code=400, detail="at least one user message required")

    prompt = user_parts[-1]
    context: dict[str, Any] = {}
    if system_parts:
        context["system"] = "\n\n".join(system_parts)
    # Include recent history (excluding last user msg) for continuity.
    history_msgs = req.messages[:-1] if req.messages[-1].role == "user" else req.messages
    if len(history_msgs) > 1:
        context["history"] = [
            {"role": m.role, "content": _extract_text(m.content)}
            for m in history_msgs if m.role in ("user", "assistant")
        ]

    crew_name = _resolve_crew(req.model) or classify_task(prompt)
    user_id = req.user or DEFAULT_USER_ID

    try:
        result = run_crew_by_name(crew_name, prompt, context)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"crew '{crew_name}' failed: {exc}")

    now = int(time.time())
    text = str(result)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": now,
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "x_super_agent": {"crew_used": crew_name, "user_id": user_id},
    }
