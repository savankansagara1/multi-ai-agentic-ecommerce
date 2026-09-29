from typing import Literal
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

load_dotenv()

from app.agents.router import detect_intents
from app.agents.unknown_handler import resolve_unknown_request
from app.agents.state import AgentState
from app.agents.product_graph import build_product_graph
from app.agents.shopping_graph import build_shopping_graph
from app.agents.order_graph import build_order_graph
from app.agents.support_graph import build_support_graph


def build_main_graph(db, with_checkpointer: bool = True, checkpointer: MemorySaver | None = None):
    product_graph = build_product_graph(db)
    shopping_graph = build_shopping_graph(db)
    order_graph = build_order_graph(db)
    support_graph = build_support_graph(db)

    # -------------------------------------------------------------
    # 1. ROUTER NODE
    # -------------------------------------------------------------
    def router_node(state: AgentState):
        # State-changing confirmation bypass:
        # If the user is currently in a confirmation or disambiguation loop,
        # bypass intent classification to avoid misclassifying "yes", "no", "1", etc.
        if state.get("awaiting_confirmation") or state.get("active_options"):
            domain = state.get("pending_domain") or "shopping"
            return {"intent": domain}

        detected = detect_intents(state["message"])
        if len(detected) >= 2:
            return {"intent": "multi_intent", "intents": detected}

        return {"intent": detected[0] if detected else "unknown"}

    # -------------------------------------------------------------
    # 2. ROUTING FUNCTION
    # -------------------------------------------------------------
    def route_request(
        state: AgentState,
    ) -> Literal[
        "product",
        "shopping",
        "order",
        "support",
        "multi_intent",
        "unknown",
    ]:
        intent = state.get("intent", "unknown")
        if intent == "multi_intent":
            return "multi_intent"
        return intent

    # -------------------------------------------------------------
    # 3. DOMAIN NODES
    # -------------------------------------------------------------
    def product_node(state: AgentState):
        result = product_graph.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": state["message"],
                    }
                ]
            }
        )
        final_message = result["messages"][-1]
        response_text = final_message.content if hasattr(final_message, "content") else str(final_message)

        return {
            "response": response_text
        }

    def shopping_node(state: AgentState):
        result = shopping_graph.invoke(state)
        return result

    def order_node(state: AgentState):
        result = order_graph.invoke(state)
        return result

    def support_node(state: AgentState):
        result = support_graph.invoke(state)
        return result

    def multi_intent_node(state: AgentState):
        intents = state.get("intents", [])
        domain_headers = {
            "shopping": "🛒 Shopping Cart",
            "order": "📦 Order Details",
            "support": "ℹ️ Customer Support & Policies",
            "product": "🔍 Product Catalog",
        }
        sections = []
        # Preserve child workflow state so compound requests can continue through
        # confirmation on the next turn instead of losing the pending action.
        child_state = {}
        for intent in intents:
            if intent == "shopping":
                res = shopping_node(state)
            elif intent == "order":
                res = order_node(state)
            elif intent == "support":
                res = support_node(state)
            elif intent == "product":
                res = product_node(state)
            else:
                continue

            header = domain_headers.get(intent, intent.capitalize())
            content = res.get("response", "").strip() if isinstance(res, dict) else str(res)
            if content:
                sections.append(f"### {header}\n{content}")
            if isinstance(res, dict):
                for key in ("pending_action", "awaiting_confirmation", "pending_domain",
                            "active_options", "pending_quantity", "action_to_execute"):
                    if key in res and res[key] is not None:
                        child_state[key] = res[key]

        combined_response = "\n\n---\n\n".join(sections)
        return {"response": combined_response, **child_state}

    def unknown_node(state: AgentState):
        # `unknown` means the first router could not confidently pick a domain;
        # this second-level check separates related questions from unrelated ones.
        result = resolve_unknown_request(state.get("message", ""))
        if result.get("redirect_intent"):
            result["intent"] = result["redirect_intent"]
        return result

    def route_unknown_result(state: AgentState):
        redirect = state.get("redirect_intent")
        if redirect in {"product", "shopping", "order", "support"}:
            return redirect
        return END

    # -------------------------------------------------------------
    # 4. BUILD STATE GRAPH
    # -------------------------------------------------------------
    builder = StateGraph(AgentState)

    builder.add_node("router", router_node)
    builder.add_node("product", product_node)
    builder.add_node("shopping", shopping_node)
    builder.add_node("order", order_node)
    builder.add_node("support", support_node)
    builder.add_node("multi_intent", multi_intent_node)
    builder.add_node("unknown", unknown_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_request,
        {
            "product": "product",
            "shopping": "shopping",
            "order": "order",
            "support": "support",
            "multi_intent": "multi_intent",
            "unknown": "unknown",
        },
    )

    builder.add_edge("product", END)
    builder.add_edge("shopping", END)
    builder.add_edge("order", END)
    builder.add_edge("support", END)
    builder.add_edge("multi_intent", END)
    builder.add_conditional_edges(
        "unknown",
        route_unknown_result,
        {
            "product": "product",
            "shopping": "shopping",
            "order": "order",
            "support": "support",
            END: END,
        },
    )

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)

    if with_checkpointer:
        mem = MemorySaver()
        return builder.compile(checkpointer=mem)

    return builder.compile()