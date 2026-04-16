"""
Coding Crew — powered by CrewAI
Handles: code generation, debugging, refactoring, test writing
Delegates to OpenCode container for actual file operations when needed.
"""

from crewai import Agent, Task, Crew, Process


def run(task: str, llm, context: dict) -> str:

    senior_dev = Agent(
        role="Senior Software Engineer",
        goal="Write clean, tested, production-ready code",
        backstory=(
            "You are a senior engineer with 15 years of experience. "
            "You write concise, well-documented code and always consider "
            "edge cases and performance. You prefer functional approaches "
            "and write tests alongside implementation."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    reviewer = Agent(
        role="Code Reviewer",
        goal="Identify bugs, security issues, and improvement opportunities",
        backstory=(
            "You are a meticulous code reviewer focused on correctness, "
            "security, and maintainability. You give concise, actionable feedback."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    implement_task = Task(
        description=f"Implement the following: {task}\n\nContext: {context}",
        expected_output="Working code with inline comments explaining key decisions.",
        agent=senior_dev,
    )

    review_task = Task(
        description="Review the code produced. Flag any bugs or improvements. Output the final corrected version.",
        expected_output="Final reviewed and corrected code ready for use.",
        agent=reviewer,
    )

    crew = Crew(
        agents=[senior_dev, reviewer],
        tasks=[implement_task, review_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return str(result)
