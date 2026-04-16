"""
Analysis Crew — powered by CrewAI
Handles: data analysis, metrics, KPIs, trend reports
"""

from crewai import Agent, Task, Crew, Process


def run(task: str, llm, context: dict) -> str:

    analyst = Agent(
        role="Senior Data Analyst",
        goal="Extract meaningful insights from data and context",
        backstory=(
            "You are a senior analyst who has worked across finance, technology, "
            "and enterprise operations. You identify trends, anomalies, and "
            "causation vs correlation. You are precise with numbers and "
            "always qualify confidence levels."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    strategist = Agent(
        role="Strategic Advisor",
        goal="Translate analysis into actionable business recommendations",
        backstory=(
            "You bridge data and decision-making. You take analytical findings "
            "and frame them as prioritised recommendations with clear rationale, "
            "tradeoffs, and next steps for senior leadership."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    analyse_task = Task(
        description=f"Analyse the following: {task}\n\nContext and data: {context}",
        expected_output="Structured analysis: key findings, patterns, confidence levels, gaps.",
        agent=analyst,
    )

    recommend_task = Task(
        description="Based on the analysis, produce prioritised recommendations for decision-makers.",
        expected_output="Executive summary + 3–5 prioritised recommendations with rationale.",
        agent=strategist,
    )

    crew = Crew(
        agents=[analyst, strategist],
        tasks=[analyse_task, recommend_task],
        process=Process.sequential,
        verbose=False,
    )

    return str(crew.kickoff())
