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

### Weekly @ Monday 09:00
Summarize MEMORY.md entries from the past week.
Output a brief digest: key decisions made, tasks completed, open threads.
