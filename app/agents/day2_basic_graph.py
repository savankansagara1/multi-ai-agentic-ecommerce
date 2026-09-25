from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    message: str


def first_node(state: State):
    print("FIRST NODE")
    print("State:", state)

    return {
        "message": state["message"] + " → first node"
    }


def second_node(state: State):
    print("SECOND NODE")
    print("State:", state)

    return {
        "message": state["message"] + " → second node"
    }


graph_builder = StateGraph(State)

graph_builder.add_node("first", first_node)
graph_builder.add_node("second", second_node)

graph_builder.add_edge(START, "first")
graph_builder.add_edge("first", "second")
graph_builder.add_edge("second", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    result = graph.invoke(
        {
            "message": "User request"
        }
    )

    print("\nFINAL RESULT:")
    print(result)