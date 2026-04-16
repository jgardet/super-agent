# Super-Agent Stack

## Why This

The AI agent landscape is fragmented. You have chat interfaces that can't write code, coding tools that can't remember context, and workflow automators that can't reason. Commercial solutions lock your data behind paywalls and API limits.

**Super-Agent Stack unifies these capabilities into a cohesive, self-hosted platform:**

- **Privacy First**: Your data never leaves your hardware when running local models
- **Flexible Inference**: Switch between cloud (GLM-5.1) for capability and local (glm-4.7-flash) for privacy
- **Multi-Agent Orchestration**: Specialized crews for coding, research, operations, and analysis
- **Persistent Memory**: Cross-session learning via vector database
- **Visual Automation**: Build complex workflows with n8n's drag-and-drop interface
- **Messaging Integration**: Access your agents via Telegram, Slack, or Discord
- **Open Source**: No vendor lock-in, full control, MIT-licensed orchestration

**Built for:** Developers, researchers, and power users who need AI agents that can write code, remember context, automate workflows, and integrate with existing tools—without compromising privacy or control.

## Key Features

### Intent-Aware Routing
Automatically routes tasks to specialized agent crews based on natural language intent. Ask "debug this function" and it routes to the coding crew. Ask "compare these frameworks" and it routes to research.

### Persistent Memory
Every interaction is stored in a vector database, enabling agents to learn from past context. Your coding agent remembers your preferences, your research agent builds on previous analysis.

### Flexible Model Switching
Toggle between cloud (GLM-5.1, free, zero VRAM) and local (glm-4.7-flash, RTX 4080) inference with one command. Use cloud for maximum capability, local for privacy and speed.

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

### 3. Coding Flow: Orchestrator → OpenCode

```
User: "Refactor the authentication module"
    │
    ▼
Orchestrator (coding crew)
    │
    ├─→ Analyzes task
    ├─→ Decides file operations needed
    │
    ▼
OpenClaw (ACP Protocol)
    │
    ├─→ Spawns OpenCode session
    ├─→ Mounts shared workspace volume
    │
    ▼
OpenCode Container
    │
    ├─→ Reads files from /workspace
    ├─→ Makes edits with LLM assistance
    ├─→ Writes changes back to /workspace
    │
    ▼
Result → Orchestrator → User
```

### 4. Messaging Flow: OpenClaw Gateway

```
Telegram/Slack/Discord
    │
    ├─→ User sends message
    │
    ▼
OpenClaw Gateway (ws://18789)
    │
    ├─→ Receives message
    ├─→ Classifies intent
    │
    ▼
Routes:
    ├─→ Simple query → Direct LLM response
    ├─→ Coding task → Spawn OpenCode via ACP
    ├─→ Research/Analysis → POST to Orchestrator
    ├─→ Complex workflow → Suggest n8n
    │
    ▼
Response → Messaging platform
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
    ├─→ OpenCode Agent (via ACP)
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
- `glm-5.1:cloud` - Default, free, zero VRAM (proxied to Z.ai)
- `glm-4.7-flash` - Best local model for RTX 4080 (~8 GB VRAM)
- `qwen3-coder:14b` - Heavy coding tasks (~9 GB VRAM)
- `qwen3.5:9b` - Fastest local model (~6 GB VRAM)

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
  "model": "glm-5.1:cloud",
  "prompt": "Hello, world!"
}'
```

---

### CrewAI Orchestrator: Intent Router & Multi-Agent System

**Purpose**: Classifies task intent and routes to specialized crews, manages agent collaboration.

**Intent Classification:**

| Intent | Keywords | Crew |
|--------|----------|------|
| coding | code, bug, function, script, refactor, debug, test | coding crew |
| research | research, find, search, summarize, compare, explain | research crew |
| ops | deploy, monitor, schedule, cron, email, calendar, automate | ops crew |
| analysis | analyse, data, report, chart, metrics, kpi, dashboard | analysis crew |

**API Endpoints:**

```bash
# Health check
curl http://localhost:8000/health

# Status (shows available crews, model, memory status)
curl http://localhost:8000/status

# Run task (auto-routed by intent)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a Python script to parse YAML files"}'

# Force specific crew
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare LangGraph vs CrewAI", "crew": "research"}'

# Use Claude for reasoning (requires ANTHROPIC_API_KEY)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Design a governance framework", "use_reasoning_llm": true}'

# Search memory
curl "http://localhost:8000/memory/search?query=YAML parsing&limit=5"
```

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

### Qdrant + Mem0: Vector Memory

**Purpose**: Persistent cross-session memory for context retention and retrieval.

**How It Works:**

1. **Storage**: Every task execution is automatically stored in Qdrant via Mem0
   - Task description
   - Result/output
   - Metadata (crew, model, timestamp)

2. **Embedding**: Uses `nomic-embed-text` model (274 MB) for vectorization

3. **Retrieval**: Semantic search finds relevant past context for new tasks

**Configuration:** `./config/mem0-config.yaml`

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
  "model": "glm-5.1:cloud",
  "provider": {
    "ollama": {
      "baseUrl": "http://ollama:11434"
    }
  },
  "autoshare": false,
  "experimental": {
    "multifile": true
  }
}
```

**ACP Integration:**

OpenClaw can spawn OpenCode sessions via the ACP (Agent Communication Protocol) for complex coding tasks.

---

### OpenClaw: Ops/Memory Agent & Messaging Gateway

**Purpose**: Long-running ops/memory agent with messaging channel integration.

**Components:**

1. **Gateway** (ws://localhost:18789)
   - WebSocket server for messaging
   - Routes messages to appropriate services
   - Manages agent sessions

2. **Memory** (MEMORY.md)
   - Long-term context storage
   - Session state
   - Auto-consolidation

3. **Personality** (SOUL.md, AGENTS.md)
   - Agent behavior definition
   - Routing rules
   - Boundaries

**Configuration:** `./config/openclaw-config.yaml`

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
- **OpenCode Agent**: Via ACP through OpenClaw

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

Connected to Ollama at `http://ollama:11434` automatically. Model selection happens in the UI.

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
Telegram → OpenClaw → Intent classification
                      ↓
                  Routes to:
                  - Orchestrator (research)
                  - OpenCode (coding)
                  - Direct LLM (simple)
                      ↓
                  Response → Telegram
```

Best for: Remote access, team collaboration, alerts.

---

## Configuration

### Environment Variables (.env)

```bash
# Model Mode
MODEL_MODE=cloud                    # cloud or local
CLOUD_MODEL=glm-5.1:cloud
LOCAL_MODEL=glm-4.7-flash
ACTIVE_MODEL=glm-5.1:cloud         # Auto-managed by switch-model script

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
- **OpenClaw**: `./config/openclaw-config.yaml`
- **Mem0**: `./config/mem0-config.yaml`

### Volumes

| Volume | Purpose | Location |
|--------|---------|----------|
| ollama_data | Downloaded model weights | Docker volume |
| openclaw_workspace | OpenClaw memory and state | Docker volume |
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
