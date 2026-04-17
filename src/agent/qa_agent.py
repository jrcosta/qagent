
from crewai import Agent

def create_agent(llm, tools):
    return Agent(
        role="Agnostic Code Reviewer",
        goal="Review changes and detect inconsistencies",
        backstory="Expert reviewer capable of analyzing any stack",
        tools=tools,
        llm=llm,
        verbose=True
    )
