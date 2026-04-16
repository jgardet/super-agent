# AGENTS

## Routing rules

When the user asks about code, bugs, scripts, or implementation:
→ Spawn an OpenCode ACP session: "start opencode in a thread"

When the user asks for research, analysis, or structured reports:
→ POST to http://orchestrator:8000/run with crew=research

When the user asks for multi-step workflows with tool integration:
→ Suggest building a flow in n8n at http://localhost:5678

## Memory rules
- After any significant decision or context, append a note to MEMORY.md
- Format: `[date] · [topic]: [one-sentence summary]`
- Do not store credentials, API keys, or personal data in MEMORY.md

## Confirmation thresholds
- Low risk (read, summarize, draft): auto-execute
- Medium risk (write files, call APIs): brief one-line confirmation
- High risk (delete, deploy, send messages externally): full confirmation with rollback plan
