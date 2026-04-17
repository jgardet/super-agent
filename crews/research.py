"""
Research Crew — with optional Tavily web search
If TAVILY_API_KEY is set, the researcher has live internet access.
Falls back to LLM knowledge if key is absent.
"""

import os
from crewai import Agent, Task, Crew, Process

TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")


def _get_search_tools():
    """Return Tavily search tool if key is available, else empty list."""
    if not TAVILY_KEY:
        return []
    try:
        from crewai_tools import TavilySearchTool
        return [TavilySearchTool(api_key=TAVILY_KEY)]
    except ImportError:
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
            os.environ["TAVILY_API_KEY"] = TAVILY_KEY
            return [TavilySearchResults(max_results=5)]
        except ImportError:
            return []


def run(task: str, llm, context: dict) -> str:
    search_tools = _get_search_tools()
    web_note = (
        "You have live web search — use it for current facts, news, and data."
        if search_tools else
        "No web search available. Use training knowledge; flag any recency gaps."
    )

    researcher = Agent(
        role="Senior Research Analyst",
        goal="Gather accurate, current, well-sourced information on the given topic",
        backstory=(
            "You are a senior research analyst specialising in technology, business "
            "strategy, and enterprise AI. You separate signal from noise and cite "
            f"sources when available. {web_note}"
        ),
        llm=llm,
        tools=search_tools,
        verbose=False,
        allow_delegation=False,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Transform research into clear, structured, decision-ready documents",
        backstory=(
            "You write for senior technical and business audiences (CIO/CTO level). "
            "Lead with the key finding, use structure only where it helps, "
            "and always include a concrete recommendation or next step."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    research_task = Task(
        description=f"Research thoroughly: {task}\n\nContext: {context}",
        expected_output="Structured notes: key findings, sources, data points, gaps.",
        agent=researcher,
    )

    write_task = Task(
        description="Transform notes into a structured report for a senior audience.",
        expected_output="Report: executive summary, key findings, recommendation, sources.",
        agent=writer,
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
        verbose=False,
    )

    return str(crew.kickoff())
