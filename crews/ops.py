"""
Ops Crew — powered by CrewAI
Handles: deployment planning, monitoring, scheduling, workflow automation
"""

from crewai import Agent, Task, Crew, Process


def run(task: str, llm, context: dict) -> str:

    ops_engineer = Agent(
        role="Senior DevOps / Platform Engineer",
        goal="Design reliable, observable, and automated operational workflows",
        backstory=(
            "You are a senior platform engineer with deep expertise in Docker, "
            "Kubernetes, monitoring, and process automation. You think in terms "
            "of reliability, idempotency, and observability. You write clear "
            "runbooks and prefer scripted solutions over manual steps."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    planner = Agent(
        role="Technical Project Planner",
        goal="Produce clear, sequenced action plans with rollback steps",
        backstory=(
            "You translate engineering proposals into concrete, ordered task lists "
            "with acceptance criteria and rollback procedures. Every plan you write "
            "assumes something will go wrong and accounts for it."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    design_task = Task(
        description=f"Design the operational solution for: {task}\n\nContext: {context}",
        expected_output="Technical design with components, dependencies, and risk notes.",
        agent=ops_engineer,
    )

    plan_task = Task(
        description="Turn the technical design into a sequenced action plan with rollback steps.",
        expected_output="Numbered action plan with acceptance criteria and rollback procedure.",
        agent=planner,
    )

    crew = Crew(
        agents=[ops_engineer, planner],
        tasks=[design_task, plan_task],
        process=Process.sequential,
        verbose=False,
    )

    return str(crew.kickoff())
