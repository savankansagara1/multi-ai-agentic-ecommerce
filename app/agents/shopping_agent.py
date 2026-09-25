from langchain_ollama import ChatOllama

from app.schemas.agent import (
    AddToCartRequest,
    UpdateCartRequest,
    RemoveCartRequest,
)
from app.tools.shopping_tools import create_shopping_tools


def create_shopping_agent(db):
    """Creates the shopping agent with LLM and shopping tools."""
    llm = ChatOllama(
        model="gpt-oss:120b-cloud",
        temperature=0,
    )

    tools = create_shopping_tools(db)

    add_to_cart_extractor = llm.with_structured_output(AddToCartRequest)
    update_cart_extractor = llm.with_structured_output(UpdateCartRequest)
    remove_cart_extractor = llm.with_structured_output(RemoveCartRequest)

    return {
        "llm": llm,
        "tools": tools,
        "add_extractor": add_to_cart_extractor,
        "update_extractor": update_cart_extractor,
        "remove_extractor": remove_cart_extractor,
    }