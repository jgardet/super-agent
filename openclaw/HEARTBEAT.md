# HEARTBEAT

## Scheduled tasks

### Daily @ 08:00
Check if the orchestrator is healthy:
```
curl http://orchestrator:8000/health
```
If unhealthy, send a notification via configured channel.

### Daily @ 08:05
Report active model and mode:
```
curl http://orchestrator:8000/status
```
Summarize in one line: "Stack running · model: [ACTIVE_MODEL] · mode: [MODE]"

### Nightly @ 03:00 — dreaming / memory consolidation
Reconcile the local journal with the shared vector store.

1. Read new entries in `MEMORY.md` since the last sync marker
   (`<!-- synced: YYYY-MM-DD HH:MM -->`).
2. For each entry, POST to the orchestrator:
   ```
   POST http://orchestrator:8000/memory
   { "content": "<entry>", "user_id": "super-agent",
     "source": "openclaw", "metadata": {"origin": "memory.md"} }
   ```
3. On success, move the sync marker to the last processed line.
4. If the orchestrator is unreachable, retry on the next cycle — never
   drop or duplicate entries.

This makes MEMORY.md the durable source of truth and the shared Mem0
store an eventually-consistent index that every crew can query.

### Weekly @ Monday 09:00
Summarize MEMORY.md entries from the past week.
Output a brief digest: key decisions made, tasks completed, open threads.
Also POST the digest itself to `/memory` with
`metadata.topic = "weekly-digest"` so crews can reference it.
