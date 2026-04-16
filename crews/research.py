"""
Research Crew — powered by CrewAI
Handles: summarization, analysis, comparison, explanation tasks
"""

from crewai import Agent, Task, Crew, Process


def run(task: str, llm, context: dict) -> str:

    researcher = Agent(
        role="Research Analyst",
        goal="Gather and synthesize information accurately and concisely",
        backstory=(
            "You are a senior research analyst with expertise in technology "
            "and business strategy. You separate signal from noise and "
            "produce structured, actionable summaries."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Transform research into clear, well-structured documents",
        backstory=(
            "You write clearly for senior technical and business audiences. "
            "You use headers, bullet points where appropriate, and always "
            "lead with the most important finding."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    research_task = Task(
        description=f"Research and analyse: {task}\n\nAdditional context: {context}",
        expected_output="Structured research notes with key findings, data points, and gaps.",
        agent=researcher,
    )

    write_task = Task(
        description="Transform the research notes into a clear, structured report.",
        expected_output="A well-formatted report with executive summary, key findings, and recommendations.",
        agent=writer,
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
        verbose=False,
    )

    return str(crew.kickoff())
