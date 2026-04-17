# AGENTS

## Routing rules

**Single-step tasks:**
- Code / script / debug → spawn an OpenCode ACP session
- Research / explain / compare → POST `/run` with `crew=research`
- Deploy / automate / schedule → POST `/run` with `crew=ops`
- Data / metrics / KPIs → POST `/run` with `crew=analysis`

**Multi-step or ambiguous goals:**
→ POST `/run` with `crew=planner` (or omit `crew` — the planner is
auto-detected from keywords like "plan", "strategy", "roadmap",
"prepare a", "end-to-end"). The planner decomposes the goal into an
ordered DAG of up to 6 subtasks, dispatches each to a specialist
crew, then synthesises the outputs into a single deliverable.

**Tool-heavy, scheduled, or webhook-driven flows:**
→ Suggest building a flow in n8n at http://localhost:5678.

## Job queue usage

All orchestrator calls are async. `POST /run` returns a `job_id`
immediately.

- Short / interactive turns (OpenClaw, n8n webhooks): send `"sync": true`
  in the body and the orchestrator blocks up to 120 s before returning
  the finished result.
- Long-running work (planner, heavy research, reasoning LLM): leave
  `sync` unset and poll `GET /jobs/{job_id}` until `status=="done"`.

```
POST http://orchestrator:8000/run
{"prompt": "...", "crew": "planner", "user_id": "super-agent"}

GET  http://orchestrator:8000/jobs/{job_id}
GET  http://orchestrator:8000/jobs?limit=20
```

## Web search

The `research` crew has live internet access when `TAVILY_API_KEY` is
set in `.env`. When answering questions that need current information,
prefer routing to `research` and tell the user:
> "I can search the web for current information."

Check `GET /status` → `"tavily_search": true` to confirm it is wired.

## Memory rules

Memory is shared across the whole stack. Two stores, kept in sync:

1. **MEMORY.md** — human-readable journal, local to OpenClaw.
2. **Shared Mem0 store** — vector memory hosted by the orchestrator at
   `http://orchestrator:8000/memory`, consumed by every crew and by n8n.

### Recall (before answering)
For any non-trivial request, first query the shared store:
```
GET http://orchestrator:8000/memory/search?query=<topic>&user_id=super-agent&limit=5
```
Fold the returned `results[*].memory` into your reasoning. If nothing
relevant comes back, proceed without it — do not fabricate context.

### Write (after a significant turn)
Dual-write every meaningful decision, fact, or user preference:

1. Append a line to `MEMORY.md` in the format
   `[YYYY-MM-DD] · [topic]: [one-sentence summary]`.
2. POST the same summary to the shared store so crews can see it:
```
POST http://orchestrator:8000/memory
Content-Type: application/json
{
  "content": "<one-sentence summary>",
  "user_id": "super-agent",
  "source": "openclaw",
  "metadata": {"topic": "<topic>", "channel": "<telegram|slack|webchat|...>"}
}
```

### What counts as "significant"
- User preferences (tools, style, models, naming)
- Architectural or product decisions
- Ongoing threads that will resume in a later session
- Errors/resolutions worth remembering

### What NEVER goes into either store
- Credentials, API keys, tokens, secrets
- Personal data beyond what the user has explicitly shared for this stack
- Raw transcripts of messaging channels

### Failure handling
If the orchestrator is unreachable, still write to `MEMORY.md`; the
nightly dreaming job (see HEARTBEAT.md) will replay unsynced entries.

## Confirmation thresholds
- Low risk (read, summarize, draft): auto-execute
- Medium risk (write files, call APIs): brief one-line confirmation
- High risk (delete, deploy, send messages externally): full confirmation with rollback plan
