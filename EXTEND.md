# Extending the Super-Agent Stack

The Super-Agent Stack is designed to be modular and extensible. This document covers the primary ways to customize and extend its capabilities.

---

## 0. Use the Planner Meta-Crew

The planner crew (`crews/planner.py`) is a meta-orchestrator that decomposes high-level goals into sequenced subtasks, dispatches each to a specialist crew, then synthesises all outputs into a unified deliverable.

### When to Use the Planner

- **Multi-step goals**: "Prepare a roadmap to add Redis-backed job persistence"
- **Strategy and planning**: "End-to-end plan to migrate the stack to Kubernetes"
- **Ambiguous requests**: The planner can decompose unclear requests into concrete subtasks
- **Cross-domain workflows**: Tasks that span coding, research, ops, and analysis

### How It Works

1. **Decomposition**: The planner uses the LLM to break the goal into an ordered DAG of up to 6 subtasks, each assigned to a specialist crew (coding, research, ops, analysis).
2. **Execution**: Subtasks execute sequentially, with context hand-off between steps (outputs of earlier steps are passed as context to dependent steps).
3. **Synthesis**: All step outputs are combined by an executive advisor agent into a single, coherent response.

### Usage

```bash
# Auto-detected by keywords (plan, roadmap, strategy, end-to-end)
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Prepare a roadmap to add Redis-backed job persistence"}'

# Explicitly invoke the planner
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Design a governance framework", "crew": "planner"}'
```

### Customizing the Planner

Edit `crews/planner.py` to:
- Adjust the maximum number of steps (currently 6)
- Add new crew types to the `VALID_CREWS` list
- Modify the decomposition prompt to change how goals are broken down
- Change the synthesizer's tone or output format

---

## 1. Add Custom Crews

Create specialized agent crews for specific tasks. Each crew is a Python file in `./crews/` with a standard interface.

### Example - Creating a Security Analysis Crew

```python
# crews/security.py
from crewai import Agent, Task, Crew, Process

def run(task: str, llm, context: dict) -> str:
    security_expert = Agent(
        role="Security Analyst",
        goal="Identify vulnerabilities and security risks",
        backstory="Expert in application security, penetration testing, and threat modeling",
        llm=llm
    )
    
    analysis_task = Task(
        description=task,
        expected_output="Detailed security analysis with identified risks and recommendations",
        agent=security_expert
    )
    
    crew = Crew(
        agents=[security_expert],
        tasks=[analysis_task],
        process=Process.sequential
    )
    
    return str(crew.kickoff())
```

### Usage

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze this code for security vulnerabilities", "crew": "security"}'
```

**No restart required** - the orchestrator hot-loads crews on demand.

### Crew Structure

Each crew must implement the standard interface:

```python
def run(task: str, llm, context: dict) -> str:
    """
    Args:
        task: The user's prompt/task description
        llm: The LangChain LLM instance (Ollama or Anthropic)
        context: Optional dictionary with additional context
    
    Returns:
        str: The crew's output/result
    """
    # Your implementation
    return result
```

### Best Practices

- Keep crews focused on single responsibilities
- Use descriptive agent roles and backstories
- Define clear expected outputs for tasks
- Test crews with various prompt types
- Consider adding hierarchical processes for complex tasks

---

## 2. Use the Async Job Queue

The orchestrator runs all crew tasks in a background thread pool (`ThreadPoolExecutor`, default 4 workers, configurable via `ORCHESTRATOR_WORKERS`). This allows long-running tasks (planner, heavy research, reasoning LLM) to run without blocking.

### Async vs Sync Mode

**Async mode** (default): Submit a task and get a `job_id` immediately. Poll for the result.

```bash
# Submit task
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Prepare a roadmap to add Redis-backed job persistence"}'
# Response: {"job_id": "...", "status": "queued", ...}

# Poll for result
curl http://localhost:8000/jobs/{job_id}
# Response: {"job_id": "...", "status": "done", "result": "...", ...}
```

**Sync mode** (for OpenClaw, n8n webhooks, or any caller that needs an inline answer): Set `"sync": true` and the orchestrator blocks up to `ORCHESTRATOR_SYNC_TIMEOUT` seconds (default 120) before returning.

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarise CrewAI vs LangGraph", "crew": "research", "sync": true}'
# Response: {"job_id": "...", "status": "done", "result": "...", ...}
```

### Job Management Endpoints

```bash
# Get job status and result
GET /jobs/{job_id}

# List recent jobs (newest first, capped at limit)
GET /jobs?limit=20

# Delete a finished job from memory
DELETE /jobs/{job_id}
```

### Scaling the Job Queue

- Increase workers: Set `ORCHESTRATOR_WORKERS=8` in `.env` (or higher if you have CPU headroom).
- For multi-replica setups, swap the in-memory `_jobs` dict for Redis (add a Redis service to docker-compose.yml and update `orchestrator/main.py` to use it).

---

## 3. Enable Web Search with Tavily

The research crew can perform live web searches when `TAVILY_API_KEY` is configured. This allows agents to answer questions requiring current information, news, or real-time data.

### Setup

1. Get a free API key at [tavily.com](https://tavily.com) (1000 searches/month on the free tier).
2. Add to `.env`:
```bash
TAVILY_API_KEY=your_tavily_key_here
```
3. Restart the orchestrator:
```bash
docker compose restart orchestrator
```

### Verification

Check that web search is wired:
```bash
curl http://localhost:8000/status
# Expect: "tavily_search": true
```

### Usage

The research crew automatically uses web search when the task requires current information. No additional parameters needed—just route to the research crew:

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are the latest developments in CrewAI?", "crew": "research"}'
```

### Customizing Web Search

Edit `crews/research.py` to:
- Attach the `crewai_tools.TavilySearchTool` to the researcher agent (currently the crew expects the tool to be available via environment).
- Adjust search parameters (max results, search depth, include images, etc.).
- Combine web search results with the agent's knowledge base.

### Rate Limits

The free Tavily tier allows 1000 searches/month. Monitor usage via the Tavily dashboard. For higher volume, upgrade to a paid plan or implement caching in your workflows (e.g., store frequently-searched topics in memory).

---

## 4. Build n8n Workflows

Create visual automation workflows using n8n's drag-and-drop interface.

**Access:** http://localhost:5678

### Common Extensions

- **Scheduled Reports**: Daily/weekly automated analysis
- **External API Integration**: Connect to Jira, GitHub, Slack, email
- **Data Pipelines**: ETL workflows with AI processing
- **Multi-Step Automation**: Chain multiple agent operations

### Example Workflow

```
Webhook Trigger
    ↓
Orchestrator (research crew)
    ↓
Parse results
    ↓
Ollama (summarize)
    ↓
Memory (store)
    ↓
Slack notification
```

### Key Integrations

- **Orchestrator Node**: HTTP Request to `http://orchestrator:8000/run`
- **Ollama Node**: HTTP Request to `http://ollama:11434/api/generate`
- **Memory Node**: HTTP Request to `http://orchestrator:8000/memory/search`
- **OpenCode Agent**: Via ACP through OpenClaw

### Sharing Workflows

Export workflows and share them via GitHub issues or the community for others to import.

---

## 5. Add Messaging Channels

Configure OpenClaw to support additional messaging platforms.

### Steps

1. Add bot token to `.env`:
```bash
DISCORD_BOT_TOKEN=your_discord_token
```

2. Update `./config/openclaw-config.yaml`:
```yaml
channels:
  discord:
    enabled: true
    token: "${DISCORD_BOT_TOKEN}"
```

3. Restart OpenClaw:
```bash
docker compose restart openclaw
```

### Supported Channels

- Telegram
- Slack
- Discord
- Custom WebSocket clients

### Channel Configuration

Each channel in `openclaw-config.yaml` can be configured with:

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
    # Optional: specific settings
    allowed_users:
      - user_id_1
      - user_id_2
```

---

## 6. Add New Services

Integrate additional services into the Docker Compose stack.

### Example - Adding a Monitoring Service

Edit `docker-compose.yml`:
```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: sa-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - super-agent
    restart: unless-stopped
```

### Considerations

- Use the `super-agent` network for inter-service communication
- Add health checks for production reliability
- Document new service endpoints in README
- Use environment variables for configuration
- Add proper volume mounts for persistence

### Common Additions

- **Prometheus + Grafana**: Monitoring and visualization
- **Redis**: Caching layer for performance
- **PostgreSQL**: Persistent data storage
- **Elasticsearch**: Advanced search capabilities
- **MinIO**: Object storage for files

---

## 7. Add Custom LLM Models

Add new models to Ollama for specialized tasks.

### Pull a Model

```bash
docker exec -it sa-ollama ollama pull mistral
```

### Available Models

Browse available models at [ollama.com/library](https://ollama.com/library)

Popular options:
- `mistral` - General purpose, efficient
- `llama2` - Meta's LLaMA 2
- `codellama` - Specialized for code
- `neural-chat` - Conversational AI

### Use in Crew

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "your task", "use_reasoning_llm": true}'
```

### Switch Default Model

```bash
./scripts/switch-model.sh local mistral
```

Or for Windows:
```powershell
.\scripts\switch-model.ps1 local mistral
```

### Model Selection Guidelines

- **Small models (3-7B)**: Faster inference, lower VRAM
- **Medium models (7-14B)**: Balance of speed and capability
- **Large models (30B+)**: Best capability, requires significant VRAM
- **Specialized models**: Domain-specific (code, math, etc.)

---

## 8. Configure Memory Patterns

Customize how Mem0 stores and retrieves context.

### Edit `./config/mem0-config.yaml`

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

memory:
  top_k: 5              # Number of results to retrieve
  metadata:
    user_id: true        # Track per-user memory
    session_id: true     # Track session context
    tags: true           # Enable custom tags

history:
  num_turns: 3           # Conversation history depth
```

### Use Cases

- **Per-user memory**: Track memory separately for different users
- **Session isolation**: Keep context within specific sessions
- **Custom metadata**: Add tags for filtering and organization
- **Adjustable retrieval**: Control how much context is retrieved

### Memory Search API

```bash
curl "http://localhost:8000/memory/search?query=your search term&limit=5"
```

---

## 9. Create OpenClaw Agents

Build custom agents that communicate via the ACP (Agent Communication Protocol).

### Agent Template

```javascript
// my-agent/index.js
const { Agent } = require('@openclaw/sdk');

const agent = new Agent({
  name: 'my-agent',
  capabilities: ['file_read', 'file_write'],
  handler: async (task) => {
    // Handle task
    return { result: 'completed' };
  }
});

agent.start();
```

### Register in `openclaw-config.yaml`

```yaml
acp:
  enabled: true
  allowed_agents:
    - opencode
    - my-agent
```

### Capabilities

Define what your agent can do:
- `file_read`: Read files from workspace
- `file_write`: Write files to workspace
- `http_request`: Make HTTP requests
- `shell_exec`: Execute shell commands
- Custom capabilities as needed

### Agent Communication

Agents communicate via WebSocket on port 18789. The ACP protocol defines:
- Task assignment
- Result reporting
- Error handling
- Capability negotiation

---

## 9. Add API Integrations

Extend the orchestrator with custom API endpoints.

### Edit `orchestrator/main.py`

```python
from pydantic import BaseModel

class CustomRequest(BaseModel):
    param1: str
    param2: int

@app.post("/custom-endpoint", tags=["custom"])
def custom_handler(req: CustomRequest):
    # Your custom logic
    result = process_request(req)
    return {"result": result}
```

### Add to OpenAPI Schema

Custom endpoints automatically appear in the Swagger UI at http://localhost:8000/docs

### Rebuild Orchestrator

```bash
docker compose build orchestrator
docker compose up -d orchestrator
```

### Best Practices

- Use Pydantic models for request/response validation
- Add proper error handling
- Document endpoints with docstrings
- Use appropriate HTTP methods (GET, POST, PUT, DELETE)
- Add authentication if needed

---

## 11. Modify Crew Behavior

Enhance existing crews with additional agents or tasks.

### Example - Adding a Tester to Coding Crew

Edit `crews/coding.py`:

```python
from crewai import Agent, Task, Crew, Process

def run(task: str, llm, context: dict) -> str:
    developer = Agent(
        role="Senior Software Engineer",
        goal="Write clean, efficient, and well-documented code",
        backstory="Expert in Python, JavaScript, and system design",
        llm=llm
    )
    
    reviewer = Agent(
        role="Code Reviewer",
        goal="Review code for quality, security, and best practices",
        backstory="Senior engineer with 10+ years of code review experience",
        llm=llm
    )
    
    tester = Agent(
        role="QA Engineer",
        goal="Write comprehensive tests for the code",
        backstory="Expert in testing frameworks and quality assurance",
        llm=llm
    )
    
    dev_task = Task(
        description=task,
        expected_output="Production-ready code with documentation",
        agent=developer
    )
    
    review_task = Task(
        description="Review the code for issues and improvements",
        expected_output="Review comments and suggested changes",
        agent=reviewer
    )
    
    test_task = Task(
        description="Write unit and integration tests",
        expected_output="Test suite with high coverage",
        agent=tester
    )
    
    crew = Crew(
        agents=[developer, reviewer, tester],
        tasks=[dev_task, review_task, test_task],
        process=Process.sequential
    )
    
    return str(crew.kickoff())
```

### Process Modes

CrewAI supports different process modes:

- **Sequential**: Tasks execute one after another
- **Hierarchical**: Manager agent delegates to worker agents
- **Custom**: Define your own process logic

### Adding Context

Pass additional context to crews:

```python
def run(task: str, llm, context: dict) -> str:
    # Access context
    user_id = context.get('user_id')
    project = context.get('project')
    
    # Use context in agent configuration
    agent = Agent(
        role="Developer",
        backstory=f"Working on project: {project}",
        llm=llm
    )
```

---

## 12. Extension Guidelines

### Best Practices

- **Keep crews focused**: Single responsibility per crew
- **Use environment variables**: For configuration and secrets
- **Add health checks**: For custom services in production
- **Document components**: Update README with new features
- **Test in isolation**: Verify extensions before integration
- **Version control**: Track changes to custom components
- **Error handling**: Graceful degradation when services fail

### Testing Extensions

```bash
# Test crew
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "crew": "your_crew"}'

# Test service health
docker compose ps

# View logs
docker compose logs <service>
```

### Performance Considerations

- **Model selection**: Smaller models for frequent tasks
- **Caching**: Use Redis for repeated queries
- **Async operations**: Use async/await for I/O-bound tasks
- **Resource limits**: Set appropriate Docker resource constraints
- **Memory management**: Monitor Qdrant storage growth

### Security Considerations

- **API keys**: Never commit secrets to git
- **Network isolation**: Use Docker networks appropriately
- **Authentication**: Add auth to public-facing endpoints
- **Input validation**: Validate all user inputs
- **Rate limiting**: Protect against abuse

---

## Community Contributions

We welcome community contributions to extend the Super-Agent Stack!

### Ways to Contribute

- **Share crews**: Submit useful crew definitions via GitHub issues
- **Workflow templates**: Contribute n8n workflow examples
- **Documentation**: Improve docs and add examples
- **Bug reports**: Report issues with detailed reproduction steps
- **Feature requests**: Propose new capabilities
- **Pull requests**: Submit code improvements

### Contribution Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request with description

### Sharing Extensions

When sharing extensions, include:
- Clear description of what it does
- Installation/usage instructions
- Example inputs and outputs
- Dependencies or requirements
- License information

---

## Resources

- **CrewAI Documentation**: https://docs.crewai.com
- **Ollama Documentation**: https://github.com/ollama/ollama
- **n8n Documentation**: https://docs.n8n.io
- **Qdrant Documentation**: https://qdrant.tech/documentation
- **Mem0 Documentation**: https://docs.mem0.ai
- **OpenClaw Documentation**: https://github.com/openclaw-ai/openclaw

---

## Support

For questions about extending the stack:
- Check existing GitHub issues
- Start a new discussion
- Refer to component documentation above
