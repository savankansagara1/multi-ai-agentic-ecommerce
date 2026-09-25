from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.product_agent import create_product_agent


class ProductAgentState(MessagesState):
    pass


def build_product_graph(db):

    llm, tools = create_product_agent(db)

    tool_node = ToolNode(tools)

    def product_agent_node(state: ProductAgentState):

        response = llm.invoke(state["messages"])

        return {
            "messages": [response]
        }

    builder = StateGraph(ProductAgentState)

    builder.add_node("agent", product_agent_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(
        START,
        "agent"
    )

    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge(
        "tools",
        "agent"
    )

    return builder.compile()