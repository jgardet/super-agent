# AGENTS

## Routing rules

When the user asks about code, bugs, scripts, or implementation:
→ Spawn an OpenCode ACP session: "start opencode in a thread"

When the user asks for research, analysis, or structured reports:
→ POST to http://orchestrator:8000/run with crew=research

When the user asks for multi-step workflows with tool integration:
→ Suggest building a flow in n8n at http://localhost:5678

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
