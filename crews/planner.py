"""
Planner crew — meta-orchestrator
Takes a high-level goal, decomposes it into sequenced subtasks,
calls the appropriate specialist crew for each, then synthesises
all results into a unified deliverable.

This is the piece that makes the stack feel like a real assistant
rather than a router. It runs as crew="planner" or is invoked
automatically for multi-step prompts detected by the orchestrator.
"""

from __future__ import annotations

import json
import re
from typing import Any

from crewai import Agent, Task, Crew, Process


# ── Decomposer ────────────────────────────────────────────────────────────────

def _decompose(goal: str, llm) -> list[dict]:
    """
    Ask the LLM to break the goal into ordered subtasks.
    Returns a list of {"step": int, "crew": str, "task": str, "depends_on": [int]}
    """
    VALID_CREWS = ["coding", "research", "ops", "analysis"]

    decomposer = Agent(
        role="Task Decomposition Specialist",
        goal="Break complex goals into ordered, executable subtasks routed to specialist crews",
        backstory=(
            "You are an expert at decomposing ambiguous goals into clear, sequenced "
            "subtasks. Each subtask must be concrete, actionable, and assignable to "
            "exactly one specialist crew. You think about dependencies — what must "
            "be done before what — and you keep the plan minimal: no redundant steps."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    decompose_task = Task(
        description=f"""
Decompose this goal into an ordered list of subtasks:

GOAL: {goal}

Available crews and what they handle:
- research : web lookup, summarisation, comparison, explanation
- analysis  : data interpretation, KPIs, trends, recommendations
- coding    : code generation, scripts, debugging, APIs
- ops       : deployment plans, scheduling, workflow automation

Rules:
1. Return ONLY a JSON array, no prose, no markdown fences.
2. Each item: {{"step": <int>, "crew": "<crew>", "task": "<concrete instruction>", "depends_on": [<step ints>]}}
3. depends_on is empty [] for the first step(s) that can run independently.
4. Maximum 6 steps. If the goal can be achieved in 1 step, use 1 step.
5. crew must be one of: {VALID_CREWS}
""",
        expected_output="A JSON array of subtask objects.",
        agent=decomposer,
    )

    crew = Crew(
        agents=[decomposer],
        tasks=[decompose_task],
        process=Process.sequential,
        verbose=False,
    )
    raw = str(crew.kickoff())

    # Extract JSON array robustly
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        # Fallback: single research step
        return [{"step": 1, "crew": "research", "task": goal, "depends_on": []}]

    try:
        steps = json.loads(match.group())
        # Validate crew names
        for s in steps:
            if s.get("crew") not in VALID_CREWS:
                s["crew"] = "research"
        return steps
    except json.JSONDecodeError:
        return [{"step": 1, "crew": "research", "task": goal, "depends_on": []}]


# ── Synthesiser ───────────────────────────────────────────────────────────────

def _synthesise(goal: str, step_results: list[dict], llm) -> str:
    """Combine all step outputs into a coherent final deliverable."""

    synthesiser = Agent(
        role="Senior Executive Advisor",
        goal="Synthesise multi-step research and analysis into a clear, actionable output",
        backstory=(
            "You distil complex multi-source inputs into executive-quality deliverables. "
            "You lead with the answer, structure information logically, and cut anything "
            "that doesn't serve the decision-maker. You write for a CIO/CTO audience."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    steps_summary = "\n\n".join(
        f"--- Step {r['step']} ({r['crew']} crew): {r['task']} ---\n{r['result']}"
        for r in step_results
    )

    synth_task = Task(
        description=f"""
Original goal: {goal}

Results from each step:
{steps_summary}

Produce the final unified deliverable. Be concise. Lead with the most important finding
or recommendation. Use headers and bullet points only where they genuinely help clarity.
Do not summarise what the steps did — give the actual answer/output.
""",
        expected_output="A complete, executive-quality response to the original goal.",
        agent=synthesiser,
    )

    crew = Crew(
        agents=[synthesiser],
        tasks=[synth_task],
        process=Process.sequential,
        verbose=False,
    )
    return str(crew.kickoff())


# ── Main entry point ──────────────────────────────────────────────────────────

def run(task: str, llm, context: dict) -> str:
    """
    Planner entry point — called by the orchestrator as any other crew.
    The orchestrator passes run_crew() callbacks via context if available;
    otherwise this module imports them directly to avoid circular deps.
    """
    # Import here to avoid circular import at module load time
    from orchestrator_bridge import run_crew_by_name  # injected by main.py

    # 1. Decompose the goal
    steps = _decompose(task, llm)

    if len(steps) == 1:
        # Single step — no need for planner overhead, delegate directly
        return run_crew_by_name(steps[0]["crew"], steps[0]["task"], context)

    # 2. Execute steps respecting dependencies (sequential for now)
    #    Steps with no depends_on run first; then in order.
    completed: dict[int, str] = {}
    step_results: list[dict] = []

    sorted_steps = sorted(steps, key=lambda s: (len(s.get("depends_on", [])), s["step"]))

    for step in sorted_steps:
        step_num = step["step"]
        crew_name = step["crew"]
        step_task = step["task"]

        # Enrich context with outputs of dependencies
        dep_context = dict(context)
        for dep in step.get("depends_on", []):
            if dep in completed:
                dep_context[f"step_{dep}_result"] = completed[dep]

        result = run_crew_by_name(crew_name, step_task, dep_context)
        completed[step_num] = result
        step_results.append({
            "step": step_num,
            "crew": crew_name,
            "task": step_task,
            "result": result,
        })

    # 3. Synthesise all results
    return _synthesise(task, step_results, llm)
