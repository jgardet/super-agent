# Super-Agent Stack

## Why This

The AI agent landscape is fragmented. You have chat interfaces that can't write code, coding tools that can't remember context, and workflow automators that can't reason. Commercial solutions lock your data behind paywalls and API limits.

**Super-Agent Stack unifies these capabilities into a cohesive, self-hosted platform:**

- **Privacy First**: Your data never leaves your hardware when running local models
- **Flexible Inference**: Switch between cloud (Ollama-Cloud models) for capability and local GPU models for privacy
- **Multi-Agent Orchestration**: Specialized crews for coding, research, operations, and analysis
- **Persistent Memory**: Cross-session learning via vector database
- **Visual Automation**: Build complex workflows with n8n's drag-and-drop interface
- **Messaging Integration**: Access your agents via Telegram, Slack, or Discord
- **Open Source**: No vendor lock-in, full control, MIT-licensed orchestration

**Built for:** Developers, researchers, and power users who need AI agents that can write code, remember context, automate workflows, and integrate with existing tools—without compromising privacy or control.

## Key Features

### Intent-Aware Routing
Automatically routes tasks to specialized agent crews using **LLM-based semantic understanding**. The system analyzes the meaning of your request rather than just matching keywords, enabling accurate routing of complex or ambiguous tasks. Ask "debug this function" and it routes to the coding crew. Ask "compare these frameworks" and it routes to research.

### Persistent Memory
Every interaction is stored in a vector database, enabling agents to learn from past context. Your coding agent remembers your preferences, your research agent builds on previous analysis.

### Flexible Model Switching
Toggle between cloud (Ollama-Cloud, zero VRAM) and local (any model that fits your GPU) inference with one command. Use cloud for maximum capability, local for privacy and speed.

### Real File Operations
The coding agent can actually read, edit, and create files in your workspace. Not just code generation—real file system operations with LLM guidance.

### Visual Workflow Automation
Build complex multi-step pipelines with n8n's drag-and-drop interface. Schedule daily reports, automate code maintenance, integrate with external APIs.

### Multi-Channel Access
Interact with your agents via web chat, Telegram, Slack, or Discord. The same intelligent agents, accessible from anywhere.

### Complete Privacy
When running local models, your data never leaves your hardware. No API calls to external services, no data training on your inputs.

### Zero Configuration
Docker Compose handles everything. One command to start, one command to switch models. No complex setup, no dependency hell.

> **Legal Notice**: This project integrates third-party software components, each licensed under their own terms. See the [License](#license) section for details on third-party licenses and attribution requirements.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Component Interoperation](#component-interoperation)
- [Quick Start](#quick-start)
- [Component Deep Dive](#component-deep-dive)
- [Extending the Stack](#extending-the-stack) *(see [EXTEND.md](EXTEND.md) for details)*
- [Activity Patterns](#activity-patterns)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interfaces                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Open-WebUI (Chat)    │    n8n (Workflows)    │    OpenClaw (Messaging)   │
│  http://localhost:3000│  http://localhost:5678│  ws://localhost:18789     │
└────────────┬──────────┴────────────┬───────────┴────────────┬──────────────┘
             │                       │                        │
             └───────────────────────┴────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │      CrewAI Orchestrator         │
                    │      (Intent Router)             │
                    │      http://localhost:8000       │
                    └────────────────┬─────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
    ┌───────▼──────┐      ┌────────▼────────┐      ┌──────▼──────┐
    │   Ollama     │      │     Qdrant       │      │  OpenCode   │
    │  (LLM Server)│      │  (Vector Memory) │      │ (Coding)    │
    │ :11434       │      │     :6333        │      │  Container   │
    └──────────────┘      └─────────────────┘      └─────────────┘
```

### Core Components

| Component | Purpose | Technology | Port | Repo | License |
|-----------|---------|------------|------|------|---------|
| **Ollama** | LLM inference server (cloud proxy or local GPU) | Go | 11434 | [github.com/ollama/ollama](https://github.com/ollama/ollama) | MIT |
| **CrewAI Orchestrator** | Intent routing and multi-agent orchestration | Python/FastAPI | 8000 | [github.com/crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | MIT |
| **Qdrant** | Vector database for cross-session memory | Rust | 6333 | [github.com/qdrant/qdrant](https://github.com/qdrant/qdrant) | Apache 2.0 |
| **OpenCode** | Interactive coding agent with file operations | Node.js | - | [github.com/opencode-ai/opencode](https://github.com/opencode-ai/opencode) | MIT |
| **OpenClaw** | Ops/memory agent with messaging gateway | Node.js | 18789 | [github.com/openclaw-ai/openclaw](https://github.com/openclaw-ai/openclaw) | MIT |
| **n8n** | Visual workflow automation | Node.js | 5678 | [github.com/n8n-io/n8n](https://github.com/n8n-io/n8n) | Fair-Code |
| **Open-WebUI** | Chat interface and model playground | Python | 3000 | [github.com/open-webui/open-webui](https://github.com/open-webui/open-webui) | MIT |

**Note**: Each component is licensed under its own license as indicated above. This repository provides orchestration and configuration for these tools but does not modify their source code.

---

## Component Interoperation

### 1. Request Flow: Chat → Orchestrator → Crew

```
User (Open-WebUI)
    │
    ├─→ "Write a Python script to parse YAML"
    │
    ▼
Orchestrator (Intent Classification)
    │
    ├─→ Detects keywords: "code", "script", "python"
    │
    ▼
Routes to: coding crew
    │
    ├─→ Loads crews/coding.py
    │
    ▼
CrewAI Execution
    │
    ├─→ Senior Dev Agent: Generates code
    ├─→ Code Reviewer Agent: Reviews and improves
    │
    ▼
Result → Stored in Mem0/Qdrant
    │
    ▼
Response to User
```

### 2. Memory Flow: Cross-Session Context

```
Task Execution
    │
    ├─→ Crew completes task
    │
    ▼
Mem0 captures:
    - Task description
    - Result/output
    - Metadata (crew, model, timestamp)
    │
    ▼
Qdrant Vector Store
    │
    ├─→ Embeds content with nomic-embed-text
    ├─→ Stores in "super_agent_memory" collection
    │
    ▼
Future Tasks
    │
    ├─→ Search: GET /memory/search?query=YAML parsing
    ├─→ Retrieves relevant past context
    │
    ▼
Enhanced context for new tasks
```

### 3. Coding Flow: Orchestrator → OpenCode (HTTP shim)

```
User: "Refactor the authentication module"
    │
    ▼
Orchestrator → coding crew (crews/coding.py)
    │
    ├─→ POST http://opencode:8787/run  (HTTP shim inside sa-opencode)
    │       (shim spawns: opencode run "<task>" in /workspace)
    │
    ▼
OpenCode container
    ├─→ Reads/creates/edits files in /workspace (shared volume)
    ├─→ Runs commands if needed (pytest, linters, etc.)
    ├─→ Returns stdout / stderr / exit_code
    │
    ▼
CrewAI reviewer agent
    ├─→ Summarises what changed, flags issues, confirms success
    │
    ▼
Result + OpenCode transcript → Orchestrator → User
```

The `/workspace` volume is mounted by both `sa-opencode` and `sa-orchestrator`,
so files written by OpenCode are immediately visible everywhere.

### 4. Messaging Flow: OpenClaw Gateway

OpenClaw runs on `ws://localhost:18789` with a pre-registered `coder` agent
backed by Ollama (via the `ollama/` provider OpenClaw wires on first boot).
The `coder` agent uses OpenClaw's built-in **coding-agent skill**: for any
coding request, it spawns `opencode run` as a bash sub-process against
`/workspace`, so file edits land on the same shared volume the orchestrator
sees.

```
Channel (Telegram / Slack / Discord)
    │
    ├─→ OpenClaw gateway :18789
    │
    ▼
Coder agent (Ollama brain via ollama/ provider)
    │
    ├─→ Intent classification
    │
    ▼
Coding-agent skill
    │
    ├─→ bash tool: opencode run "..."
    │
    ▼
File operations
    ├─→ /workspace (shared volume)
    ├─→ Visible to orchestrator + OpenCode
    │
    ▼
Response → Channel
```

The channel tokens in `.env` are optional — you can also hit the gateway
directly, e.g.:

```bash
docker exec sa-openclaw openclaw agent --agent coder --local \
    --message 'Create /workspace/hello.py with print("hi")' --json
```

### 5. Workflow Flow: n8n Integration

```
n8n Workflow
    │
    ├─→ Trigger: Webhook, schedule, manual
    │
    ▼
Nodes:
    ├─→ HTTP Request → Orchestrator API
    ├─→ HTTP Request → Ollama API
    ├─→ Memory Search (Qdrant/Mem0)
    │
    ▼
Automation:
    ├─→ Daily reports
    ├─→ Scheduled code maintenance
    ├─→ Multi-step pipelines
    │
    ▼
Output → Notifications, databases, files
```

---

## Quick Start

### Prerequisites

- Docker + Docker Compose v2
- NVIDIA drivers + [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- Verify GPU: `docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi`
- **Windows users**: PowerShell scripts provided (`.ps1`) - same functionality as bash scripts

### Installation

**Linux/macOS:**
```bash
git clone <repo-url>
cd super-agent
cp .env.example .env
docker compose up -d
./scripts/smoke-test.sh
```

**Windows (PowerShell):**
```powershell
git clone <repo-url>
cd super-agent
Copy .env.example .env
docker compose up -d
.\scripts\smoke-test.ps1
```

### First Boot

First boot takes 2–4 minutes (image pulls). Services available at:

| Service | URL | Credentials |
|---|---|---|
| Open-WebUI | http://localhost:3000 | None (auth disabled) |
| Orchestrator API | http://localhost:8000/docs | None |
| n8n | http://localhost:5678 | admin / changeme |
| Ollama | http://localhost:11434 | None |
| OpenClaw Gateway | ws://localhost:18789 | Configure in .env |
| Qdrant | http://localhost:6333 | None |

---

## Component Deep Dive

### Ollama: LLM Server

**Purpose**: Serves LLM models, either as a cloud proxy or local GPU inference.

**Models:**
- `minimax-m2.7:cloud` — current default multi-purpose cloud model (free via Ollama-Cloud, zero VRAM)
- `glm-5.1:cloud` — best open weight model for coding (free via Ollama-Cloud, zero VRAM)
- `glm-4.7-flash` — solid local model (~8 GB VRAM, MoE 30B / 3B active)
- `qwen3-coder:14b` — heavy coding tasks (~9 GB VRAM)
- `qwen3.5:9b` — fast lower-VRAM option (~6 GB VRAM)

VRAM figures are approximate — check against your own GPU before pulling.

**Switching Models:**

**Linux/macOS:**
```bash
./scripts/switch-model.sh cloud    # Cloud mode
./scripts/switch-model.sh local    # Local mode
./scripts/switch-model.sh local qwen3.5:9b  # Custom model
```

**Windows (PowerShell):**
```powershell
.\scripts\switch-model.ps1 cloud
.\scripts\switch-model.ps1 local
.\scripts\switch-model.ps1 local qwen3.5:9b
```

**API Usage:**
```bash
# List models
curl http://localhost:11434/api/tags

# Generate completion
curl http://localhost:11434/api/generate -d '{
  "model": "minimax-m2.7:cloud",
  "prompt": "Hello, world!"
}'
```

---

### CrewAI Orchestrator: Intent Router & Multi-Agent System

**Purpose**: Classifies task intent and routes to specialized crews, manages agent collaboration.

**Intent Classification:**

The orchestrator uses **LLM-based semantic routing** for intelligent task classification. It analyzes the meaning of your request rather than just matching keywords, enabling more accurate routing of complex or ambiguous tasks.

| Intent | Description | Crew |
|--------|-------------|------|
| planner | Multi-step goals requiring decomposition, strategy, roadmaps, or end-to-end workflows | planner crew |
| coding | Writing, debugging, refactoring, or testing code | coding crew |
| research | Finding information, comparing options, explaining concepts | research crew |
| ops | Deployment, automation, scheduling, file organization | ops crew |
| analysis | Data analysis, reporting, metrics, dashboards | analysis crew |

**Planner Meta-Crew:**

The planner crew takes high-level goals and breaks them into an ordered DAG of up to 6 subtasks, dispatches each to a specialist crew, then synthesises all outputs into a single executive-quality response. Use it for complex, multi-step requests like "prepare a roadmap to add Redis-backed job persistence" or "end-to-end plan to migrate the stack to Kubernetes." It can also be invoked automatically by keywords like "plan", "roadmap", "strategy", "end-to-end".

**Fallback:** If LLM classification fails, the system falls back to keyword matching to ensure reliability.

**API Endpoints:**

```bash
# Health check
curl http://localhost:8000/health

# Status (shows available crews, model, memory, Tavily, workers)
curl http://localhost:8000/status

# Run task (auto-routed by intent, returns job_id immediately)
# Memory is automatically retrieved and injected into the crew's context.
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a Python script to parse YAML files"}'

# Poll job for result (async mode)
curl http://localhost:8000/jobs/{job_id}

# List recent jobs
curl http://localhost:8000/jobs?limit=20

# Run task synchronously (wait up to 120s for result)
# Use for OpenClaw, n8n webhooks, or any caller that needs an inline answer.
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare LangGraph vs CrewAI", "crew": "research", "sync": true}'

# Force specific crew
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Design a governance framework", "crew": "planner", "user_id": "alice"}'

# Use Claude for reasoning (requires ANTHROPIC_API_KEY)
# The crew (and any recursive planner sub-steps) will use Claude.
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Design a governance framework", "use_reasoning_llm": true}'

# Search memory (with optional user_id for isolation)
curl "http://localhost:8000/memory/search?query=YAML parsing&limit=5&user_id=alice"

# Write to memory (for cross-agent coordination)
# Used by OpenClaw, n8n, or external tools to contribute context.
curl -X POST http://localhost:8000/memory \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers pytest over unittest", "user_id": "alice", "source": "openclaw"}'

# Clear memory for a user
curl -X DELETE "http://localhost:8000/memory?user_id=alice"
```

**Web Search:**

The research crew has live internet access when `TAVILY_API_KEY` is set in `.env`. Get a free key at [tavily.com](https://tavily.com) (1000 searches/month). Check `GET /status` → `"tavily_search": true` to confirm it is wired.

**Crew Structure:**

Each crew is a Python file in `./crews/` with a standard interface:

```python
# crews/my_crew.py
from crewai import Agent, Task, Crew, Process

def run(task: str, llm, context: dict) -> str:
    agent = Agent(
        role="Expert",
        goal="Achieve specific objective",
        backstory="Background and expertise",
        llm=llm
    )
    
    task_obj = Task(
        description=task,
        expected_output="Expected result format",
        agent=agent
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task_obj],
        process=Process.sequential
    )
    
    return str(crew.kickoff())
```

**Adding Custom Crews:**

1. Create `./crews/your_crew.py` with the above structure
2. No restart needed - orchestrator hot-loads crews
3. Route to it: `curl ... -d '{"prompt": "...", "crew": "your_crew"}'`

---

### Qdrant + Mem0: Shared Vector Memory

**Purpose**: Persistent cross-session memory shared across all agents (crews, OpenClaw, n8n).

**How It Works:**

1. **Storage**: Every task execution is automatically stored in Qdrant via Mem0
   - Task description and result
   - Metadata (crew, model, timestamp, source)

2. **Embedding**: Uses `nomic-embed-text` model (274 MB) for vectorization. This model is pulled automatically at stack startup in both cloud and local mode.

3. **Retrieval**: Semantic search finds relevant past context for new tasks. Before each crew run, the orchestrator queries memory and injects results into the crew's `context["memories"]` and `context["memory_summary"]`.

4. **Cross-agent coordination**: OpenClaw dual-writes to its local `MEMORY.md` and the shared store via `POST /memory`. n8n workflows can also read/write memory. Nightly sync ensures consistency.

5. **User isolation**: Memory can be namespaced by `user_id` (defaults to `super-agent`). Pass `user_id` on `/run`, `/memory/search`, and `/memory` to separate contexts.

**Configuration:** `./config/mem0-config.yaml`

Note: `${ACTIVE_MODEL}` is expanded by the orchestrator at load time (not by Mem0 itself). The config file uses the placeholder; the orchestrator reads it, substitutes env vars, and passes the resolved config to Mem0.

```yaml
vector_store:
  provider: qdrant
  config:
    host: qdrant
    port: 6333
    collection_name: super_agent_memory

llm:
  provider: ollama
  config:
    model: "${ACTIVE_MODEL}"
    ollama_base_url: "http://ollama:11434"

embedder:
  provider: ollama
  config:
    model: nomic-embed-text
    ollama_base_url: "http://ollama:11434"
```

**Usage:**

```bash
# Search memory
curl "http://localhost:8000/memory/search?query=parsing YAML files&limit=5"

# Response includes:
# - status: memory_available
# - results: Array of relevant past tasks
# - count: Number of results
```

**Memory in Context:**

Memory is automatically used to enhance future tasks with relevant past context, enabling:
- Learning from previous solutions
- Consistent behavior across sessions
- Knowledge accumulation over time

---

### OpenCode: Interactive Coding Agent

**Purpose**: Performs actual file operations in the shared workspace with LLM assistance.

**Access:**

```bash
# Interactive session
docker exec -it sa-opencode opencode

# One-shot task
docker exec -it sa-opencode opencode --message "Refactor this file" /workspace/myfile.py
```

**Workspace:**

The `./workspace/` directory is shared between:
- OpenCode container
- Orchestrator container
- Any other services that need file access

**Configuration:** `./config/opencode-config.json`

```json
{
  "model": "ollama/minimax-m2.7:cloud",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "http://ollama:11434/v1" },
      "models": {
        "minimax-m2.7:cloud": {},
        "glm-5.1:cloud": {}
      }
    }
  },
  "autoshare": false
}
```

**How the orchestrator uses OpenCode:**

A small HTTP shim (`opencode/shim.mjs`, runs inside `sa-opencode` on port 8787)
exposes `POST /run` and spawns `opencode run <prompt>` inside `/workspace`.
The orchestrator's `coding` crew (`crews/coding.py`) calls this endpoint
directly, so every `POST /run` with `crew=coding` (or `orchestrator-coding`
from Open-WebUI) executes real file operations on disk. The shim is
internal-only — not exposed to the host.

**ACP (Agent Communication Protocol):**

`opencode acp` (Zed-style JSON-RPC over stdio or a single-session TCP port)
is not used by our internal flows — the coding crew uses the lighter HTTP
shim and OpenClaw uses shell invocation. The ACP subcommand remains
available inside `sa-opencode` if you want to drive OpenCode from an
external ACP-aware client (Zed, etc.).

---

### OpenClaw: Ops/Memory Agent & Messaging Gateway

**Purpose**: Long-running ops/memory agent with messaging channel integration.

**Components:**

1. **Gateway** (ws://localhost:18789)
   - WebSocket server for messaging
   - Routes messages to appropriate services
   - Manages agent sessions

2. **Memory** (MEMORY.md + shared vector store)
   - Local human-readable journal (`MEMORY.md`) for direct inspection
   - Dual-writes to the shared Mem0/Qdrant store via `POST /memory`
   - Nightly consolidation syncs local entries to the shared store
   - Recall queries the shared store before answering

3. **Personality** (SOUL.md, AGENTS.md)
   - Agent behavior definition
   - Routing rules
   - Memory coordination rules (recall before answering, dual-write after)

**Configuration:**

The authoritative OpenClaw config is auto-generated inside the
`openclaw_state` volume at `/root/.openclaw/openclaw.json` on first boot
by `./openclaw/bootstrap.sh` — which replicates what `ollama launch
openclaw` does interactively (wires Ollama as the model provider) but works
in a headless container. `./config/openclaw-config.yaml` is kept as a
human-readable cheat-sheet of the settings we care about; OpenClaw itself
reads the JSON.

Bootstrapped JSON (abridged):

```json
{
  "gateway": { "mode": "local", "port": 18789, "bind": "loopback", "auth": { "mode": "token" } },
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://ollama:11434",
        "models": [
          { "id": "minimax-m2:cloud" },
          { "id": "glm-5.1:cloud" },
          { "id": "qwen3.5:9b" }
        ]
      }
    }
  },
  "plugins": { "entries": { "ollama": { "enabled": true } } },
  "agents": {
    "defaults": { "model": { "primary": "ollama/minimax-m2:cloud" } },
    "list": [ { "id": "main" }, { "id": "coder", "model": "ollama/minimax-m2:cloud", "workspace": "/root/.openclaw/agents/coder/workspace" } ]
  }
}
```

The reference cheat-sheet at `./config/openclaw-config.yaml`:

```yaml
gateway:
  port: 18789
  host: "0.0.0.0"

llm:
  provider: ollama
  model: "${ACTIVE_MODEL}"
  base_url: "${OLLAMA_BASE_URL}"

memory:
  long_term: /root/.openclaw/workspace/MEMORY.md
  dreaming:
    enabled: true
    consolidation_hour: 3

acp:
  enabled: true
  allowed_agents:
    - opencode
    - claude

integrations:
  orchestrator:
    url: "http://orchestrator:8000"
    enabled: true

channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
  slack:
    enabled: true
    token: "${SLACK_BOT_TOKEN}"
```

**Enabling Messaging:**

Add token to `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_token_here
# or
SLACK_BOT_TOKEN=your_token_here
```

Restart OpenClaw:
```bash
docker compose restart openclaw
```

**Scheduled Tasks:** (HEARTBEAT.md)

- Daily @ 08:00: Check orchestrator health
- Daily @ 08:05: Report active model and mode
- Weekly @ Monday 09:00: Summarize MEMORY.md entries

---

### n8n: Visual Workflow Automation

**Purpose**: No-code/low-code workflow automation and integration platform.

**Access:** http://localhost:5678 (admin / changeme)

**Key Integrations:**

- **Orchestrator Node**: HTTP Request to `http://orchestrator:8000/run`
- **Ollama Node**: HTTP Request to `http://ollama:11434/api/generate`
- **Memory Node**: HTTP Request to `http://orchestrator:8000/memory/search`
- **OpenCode (coding) Agent**: HTTP Request to `http://orchestrator:8000/run` with `{"crew":"coding", ...}` — the orchestrator then delegates to OpenCode via its internal shim

**Example Workflow:**

```
Trigger (Webhook)
    │
    ├─→ HTTP Request → Orchestrator (research crew)
    ├─→ Parse result
    ├─→ HTTP Request → Ollama (summarize)
    ├─→ HTTP Request → Memory (store)
    │
    ▼
Notification (Email/Slack)
```

**Use Cases:**

- Daily automated reports
- Scheduled code maintenance
- Multi-step data pipelines
- Integration with external APIs
- Monitoring and alerting

---

### Open-WebUI: Chat Interface

**Purpose**: Browser-based chat interface and model playground.

**Access:** http://localhost:3000

**Features:**

- Chat with any Ollama model
- Model comparison and testing
- Prompt engineering playground
- Session history
- System prompt configuration

**Configuration:**

Open-WebUI is wired to **two** backends simultaneously:

1. **Ollama** (`http://ollama:11434`) — raw model inference
   - Local models you've pulled (e.g. `qwen3.5:9b`)
   - Ollama-Cloud models (e.g. `minimax-m2.7:cloud`, `glm-5.1:cloud`) when signed into Ollama
2. **Orchestrator** (`http://orchestrator:8000/v1`, OpenAI-compatible) — multi-agent crews
   - `orchestrator-auto` — auto-route via `classify_task`
   - `orchestrator-planner` — decompose multi-step goals
   - `orchestrator-research` — find, compare, explain
   - `orchestrator-coding` — write/debug/refactor
   - `orchestrator-ops` — deployment, automation, file ops
   - `orchestrator-analysis` — data analysis, metrics, reports

The model dropdown in Open-WebUI shows all of them together; pick one per conversation.

**When to pick what:**
- *Direct Ollama model* — fast single-shot chat, prompt tuning, playground
- *`orchestrator-auto`* — let the stack decide which crew handles the request
- *`orchestrator-<crew>`* — force a specific crew (useful when auto-routing misclassifies)

**Recommended local models for 8GB VRAM:**
- `qwen3.5:9b` (~6GB) — fast, good for chat
- `glm-4.7-flash` (~8GB) — best all-round, tight on 8GB

**To pull a local model:**
```bash
docker exec sa-ollama ollama pull qwen3.5:9b
```

**To sign Ollama into Ollama Cloud** (enables `*:cloud` models):
```bash
docker exec -it sa-ollama ollama signin
```

---

## Extending the Stack

The Super-Agent Stack is designed to be modular and extensible. For detailed instructions on how to customize and extend capabilities, see [EXTEND.md](EXTEND.md).

**Quick links:**
- Add custom crews
- Build n8n workflows
- Add messaging channels
- Integrate new services
- Configure memory patterns
- Create custom agents

---

## Activity Patterns

### Pattern 1: Simple Q&A

```
User → Open-WebUI → Ollama → Response
```

Best for: Quick questions, code snippets, explanations.

### Pattern 2: Complex Coding Task

```
User → Open-WebUI → Orchestrator (coding crew)
                    ↓
                OpenCode (file operations)
                    ↓
                Result stored in memory
                    ↓
                Response
```

Best for: File editing, refactoring, multi-file changes.

### Pattern 3: Research with Memory

```
User → Open-WebUI → Orchestrator (research crew)
                    ↓
                Memory search (past context)
                    ↓
                Enhanced research
                    ↓
                Result stored in memory
                    ↓
                Response
```

Best for: Analysis, comparisons, documentation.

### Pattern 4: Automated Workflow

```
Schedule → n8n → Orchestrator (ops crew)
                  ↓
              OpenCode (maintenance)
                  ↓
              Memory (log)
                  ↓
          Notification
```

Best for: Recurring tasks, reports, maintenance.

### Pattern 5: Messaging-Triggered

```
Telegram / Slack / Discord → OpenClaw gateway → Intent classification
                                                    ↓
                                            Routes to:
                                            - `coder` agent (coding → spawns opencode run in /workspace)
                                            - Orchestrator (research / ops / analysis via POST /run)
                                            - Direct LLM turn (simple Q&A)
                                                    ↓
                                            Response → channel
```

Best for: Remote access, team collaboration, alerts.

---

## Configuration

### Environment Variables (.env)

```bash
# Model Mode
MODEL_MODE=cloud                    # cloud or local
CLOUD_MODEL=minimax-m2.7:cloud     # Target: glm-5.1:cloud when available
LOCAL_MODEL=glm-4.7-flash          # Any model that fits your GPU
ACTIVE_MODEL=minimax-m2.7:cloud    # Auto-managed by switch-model script

# API Keys (Optional)
ANTHROPIC_API_KEY=                 # For Claude reasoning
OPENAI_API_KEY=                    # For OpenClaw fallback

# n8n
N8N_USER=admin
N8N_PASSWORD=changeme

# Messaging Channels (Optional)
TELEGRAM_BOT_TOKEN=
SLACK_BOT_TOKEN=
DISCORD_BOT_TOKEN=
```

### Service-Specific Configs

- **Orchestrator**: `./orchestrator/main.py`
- **OpenCode**: `./config/opencode-config.json`
- **OpenClaw**: `./openclaw/bootstrap.sh` (first-boot seed for `~/.openclaw/openclaw.json`) — `./config/openclaw-config.yaml` is a cheat-sheet reference only
- **Mem0**: `./config/mem0-config.yaml`

### Volumes

| Volume | Purpose | Location |
|--------|---------|----------|
| ollama_data | Downloaded model weights | Docker volume |
| openclaw_state | OpenClaw state (gateway token, agents, sessions) | Docker volume |
| qdrant_data | Vector database | Docker volume |
| n8n_data | Workflow definitions | Docker volume |
| webui_data | Open-WebUI settings | Docker volume |
| workspace | Shared coding workspace | Docker volume |

---

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker compose ps

# View logs
docker compose logs --tail=50 <service>

# Restart specific service
docker compose restart <service>
```

### GPU Not Available

```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi

# Check nvidia-container-toolkit
nvidia-smi
```

### Model Pulling Issues

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Manually pull model
docker exec -it sa-ollama ollama pull glm-4.7-flash
```

### Memory Not Working

```bash
# Check Qdrant status
curl http://localhost:6333/readyz

# Check memory status in orchestrator
curl http://localhost:8000/status

# Verify mem0-config.yaml is mounted
docker exec -it sa-orchestrator cat /app/mem0-config.yaml
```

### Permission Issues (Linux)

```bash
# Fix workspace permissions
sudo chown -R $USER:$USER ./workspace
```

### Reset Everything

```bash
# Stop and remove containers
docker compose down

# Remove all data (WARNING: deletes all data)
docker compose down -v

# Remove specific volume
docker volume rm super-agent_<volume_name>
```

---

## Stopping / Resetting

```bash
docker compose down          # Stop, keep volumes
docker compose down -v       # Stop + delete all data
docker compose restart       # Restart all services
docker compose restart <service>  # Restart specific service
```

---

## Architecture Decisions

### Why CrewAI?
- Multi-agent collaboration with clear roles
- Sequential and hierarchical process modes
- Python-based, easy to extend
- Good integration with LangChain

### Why Ollama?
- Simple API, cloud proxy support
- Local GPU acceleration
- Wide model selection
- Easy model switching

### Why Qdrant?
- High-performance vector database
- Rust-based, efficient
- Good filtering capabilities
- Easy Docker deployment

### Why Mem0?
- Simple memory abstraction
- Automatic embedding
- Configurable backends
- Good metadata support

### Why n8n?
- Visual workflow builder
- Extensive integrations
- Self-hosted
- Good for automation

---

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

### Third-Party Licenses

This project integrates the following third-party components, each licensed under their own terms:

| Component | License | Link |
|-----------|---------|------|
| Ollama | MIT License | https://github.com/ollama/ollama/blob/main/LICENSE |
| CrewAI | MIT License | https://github.com/crewAIInc/crewAI/blob/main/LICENSE |
| Qdrant | Apache License 2.0 | https://github.com/qdrant/qdrant/blob/master/LICENSE |
| OpenCode | MIT License | https://github.com/opencode-ai/opencode/blob/main/LICENSE |
| OpenClaw | MIT License | https://github.com/openclaw-ai/openclaw/blob/main/LICENSE |
| n8n | Fair Code License | https://github.com/n8n-io/n8n/blob/master/LICENSE.md |
| Open-WebUI | MIT License | https://github.com/open-webui/open-webui/blob/main/LICENSE |
| Mem0 | Apache License 2.0 | https://github.com/mem0ai/mem0/blob/main/LICENSE |
| FastAPI | MIT License | https://github.com/tiangolo/fastapi/blob/master/LICENSE |
| LangChain | MIT License | https://github.com/langchain-ai/langchain/blob/master/LICENSE |
| Docker | Apache License 2.0 | https://github.com/docker/docker-ce/blob/master/LICENSE |

**Important**: The Fair Code License (n8n) restricts certain commercial uses. Please review the n8n license before using this stack for commercial purposes.

### Attribution

This repository provides:
- Docker Compose orchestration configuration
- CrewAI crew definitions (original code)
- Integration scripts and utilities
- Configuration files

All third-party components are used as-is via their official Docker images or npm packages, without modification to their source code.
