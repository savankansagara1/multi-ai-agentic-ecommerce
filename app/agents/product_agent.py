from langchain_ollama import ChatOllama

from app.tools.product_tools import create_product_tools


def create_product_agent(db):
    llm = ChatOllama(
        model="gpt-oss:120b-cloud",
        temperature=0,
    )

    tools = create_product_tools(db)
    tool_list = list(tools.values())

    llm_with_tools = llm.bind_tools(tool_list)

    return llm_with_tools, tool_list