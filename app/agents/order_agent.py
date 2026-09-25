from langchain_ollama import ChatOllama

from app.schemas.agent import OrderQueryRequest, CancelOrderRequest
from app.tools.order_tools import create_order_tools


def create_order_agent(db):
    """Creates the order agent with LLM and order tools."""
    llm = ChatOllama(
        model="gpt-oss:120b-cloud",
        temperature=0,
    )

    tools = create_order_tools(db)

    order_query_extractor = llm.with_structured_output(OrderQueryRequest)
    cancel_order_extractor = llm.with_structured_output(CancelOrderRequest)

    return {
        "llm": llm,
        "tools": tools,
        "query_extractor": order_query_extractor,
        "cancel_extractor": cancel_order_extractor,
    }

