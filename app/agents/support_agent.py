from langchain_ollama import ChatOllama
from app.tools.support_tools import create_support_tools


def create_support_agent(db):
    """Creates the customer support agent with LLM and knowledge retrieval / escalation tools."""
    llm = ChatOllama(
        model="gpt-oss:120b-cloud",
        temperature=0,
    )

    tools = create_support_tools(db)

    return {
        "llm": llm,
        "tools": tools,
    }

