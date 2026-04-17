"""
Coding Crew — routes real coding work to OpenCode.

OpenCode is itself an LLM-driven coding agent with real file-system access
to /workspace. Rather than wrapping it in another CrewAI tool-calling layer
(which is fragile on models with limited function-calling support), the
coding crew delegates the user's task directly to the OpenCode container
via the HTTP shim on http://opencode:8787 and then has a CrewAI reviewer
agent summarise / validate the result.

Flow:
    task ──► POST http://opencode:8787/run  (OpenCode does the real file ops)
          ──► CrewAI reviewer summarises + flags issues
          ──► final result returned to caller

This keeps the flow simple and model-agnostic: tool-calling is not required.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from crewai import Agent, Task, Crew, Process


OPENCODE_SHIM_URL = os.getenv("OPENCODE_SHIM_URL", "http://opencode:8787")
OPENCODE_TIMEOUT_S = int(os.getenv("OPENCODE_TIMEOUT_S", "240"))


def _opencode_run(prompt: str) -> dict[str, Any]:
    """Send a task to the OpenCode shim. Returns the raw JSON response."""
    try:
        resp = httpx.post(
            f"{OPENCODE_SHIM_URL}/run",
            json={"prompt": prompt, "cwd": "/workspace"},
            timeout=OPENCODE_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"could not reach OpenCode shim at {OPENCODE_SHIM_URL}: {exc}",
                "stdout": "", "stderr": str(exc), "exit_code": -1}
    except json.JSONDecodeError as exc:
        return {"error": f"invalid JSON from shim: {exc}",
                "stdout": "", "stderr": str(exc), "exit_code": -1}


def _format_opencode_result(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"OpenCode bridge error: {data['error']}"
    stdout = (data.get("stdout") or "").strip()
    stderr = (data.get("stderr") or "").strip()
    exit_code = data.get("exit_code", -1)
    timed_out = data.get("timed_out", False)
    parts = [f"exit_code={exit_code}"]
    if timed_out:
        parts.append("TIMED_OUT=true")
    if stdout:
        parts.append(f"--- OpenCode output ---\n{stdout}")
    if stderr:
        parts.append(f"--- OpenCode stderr ---\n{stderr}")
    return "\n".join(parts)


def run(task: str, llm, context: dict) -> str:
    # 1) Delegate real coding work to OpenCode (has /workspace access, runs tools).
    oc_data = _opencode_run(task)
    oc_summary = _format_opencode_result(oc_data)

    # If the bridge itself failed (network / container down), bail out early
    # rather than asking the LLM to "review" an error string.
    if "error" in oc_data:
        return oc_summary

    # 2) Have a CrewAI reviewer produce a concise summary + verdict.
    reviewer = Agent(
        role="Code Reviewer",
        goal="Summarise what OpenCode did, flag any bugs or concerns, confirm the task is done.",
        backstory=(
            "You are a meticulous code reviewer. You receive the raw output "
            "of an OpenCode session (file operations, commands run, stdout/stderr) "
            "and produce a clear, concise summary for the user: what changed, "
            "where, whether it looks correct, and any follow-up actions needed."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    review_task = Task(
        description=(
            f"Original user task:\n{task}\n\n"
            f"OpenCode session output:\n{oc_summary}\n\n"
            "Write a short, user-facing summary: (1) which files were "
            "created/edited in /workspace, (2) a brief verdict on correctness, "
            "(3) any follow-up the user should do. Keep it under 10 lines."
        ),
        expected_output="A concise review summary of what OpenCode produced.",
        agent=reviewer,
    )

    crew = Crew(
        agents=[reviewer],
        tasks=[review_task],
        process=Process.sequential,
        verbose=False,
    )

    review = str(crew.kickoff()).strip()
    return f"{review}\n\n---\n{oc_summary}"

