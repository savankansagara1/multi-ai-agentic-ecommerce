from typing import Literal
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

load_dotenv()

from app.agents.router import detect_intents
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
    # 1. ROUTER NODE (DYNAMIC LLM CLASSIFICATION)
    # -------------------------------------------------------------
    def router_node(state: AgentState):
        # Confirmation / disambiguation bypass:
        if state.get("awaiting_confirmation") or state.get("active_options"):
            domain = state.get("pending_domain") or "shopping"
            return {
                "intents_queue": [domain],
                "completed_responses": {},
                "intent": domain,
            }

        detected = detect_intents(state["message"])
        primary = detected[0] if len(detected) == 1 else "multi_intent"

        return {
            "intents_queue": list(detected),
            "completed_responses": {},
            "intents": list(detected),
            "intent": primary,
        }

    # -------------------------------------------------------------
    # 2. DISPATCHER HUB NODE (LOOPBACK RECEIVER)
    # -------------------------------------------------------------
    def dispatcher_node(state: AgentState):
        return {}

    # -------------------------------------------------------------
    # 3. CONDITIONAL ROUTING FUNCTION
    # -------------------------------------------------------------
    def route_next_intent(state: AgentState) -> Literal["product", "shopping", "order", "support", "aggregator", "unknown"]:
        if state.get("awaiting_confirmation") or state.get("active_options"):
            return state.get("pending_domain") or "shopping"

        queue = state.get("intents_queue") or []
        if queue:
            next_target = queue[0]
            if next_target in ["product", "shopping", "order", "support"]:
                return next_target
            return "unknown"

        completed = state.get("completed_responses") or {}
        if completed:
            return "aggregator"

        return "unknown"

    # -------------------------------------------------------------
    # 4. DOMAIN AGENT NODES (EXECUTE & ACCUMULATE)
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

        responses = dict(state.get("completed_responses") or {})
        responses["product"] = response_text
        remaining = [i for i in (state.get("intents_queue") or []) if i != "product"]

        return {
            "completed_responses": responses,
            "intents_queue": remaining,
            "response": response_text,
        }

    def shopping_node(state: AgentState):
        result = shopping_graph.invoke(state)

        # If confirmation or disambiguation required, pause immediately for user
        if result.get("awaiting_confirmation") or result.get("active_options"):
            return result

        resp_text = result.get("response", "")
        responses = dict(state.get("completed_responses") or {})
        responses["shopping"] = resp_text
        remaining = [i for i in (state.get("intents_queue") or []) if i != "shopping"]

        output = {k: v for k, v in result.items() if k not in ["completed_responses", "intents_queue"]}
        output["completed_responses"] = responses
        output["intents_queue"] = remaining
        return output

    def order_node(state: AgentState):
        result = order_graph.invoke(state)

        # If confirmation required, pause immediately for user
        if result.get("awaiting_confirmation"):
            return result

        resp_text = result.get("response", "")
        responses = dict(state.get("completed_responses") or {})
        responses["order"] = resp_text
        remaining = [i for i in (state.get("intents_queue") or []) if i != "order"]

        output = {k: v for k, v in result.items() if k not in ["completed_responses", "intents_queue"]}
        output["completed_responses"] = responses
        output["intents_queue"] = remaining
        return output

    def support_node(state: AgentState):
        result = support_graph.invoke(state)

        resp_text = result.get("response", "")
        responses = dict(state.get("completed_responses") or {})
        responses["support"] = resp_text
        remaining = [i for i in (state.get("intents_queue") or []) if i != "support"]

        output = {k: v for k, v in result.items() if k not in ["completed_responses", "intents_queue"]}
        output["completed_responses"] = responses
        output["intents_queue"] = remaining
        return output

    # -------------------------------------------------------------
    # 5. CONDITIONAL LOOPBACK EDGE
    # -------------------------------------------------------------
    def should_loop_or_pause(state: AgentState):
        if state.get("awaiting_confirmation") or state.get("active_options"):
            return END
        return "dispatcher"

    # -------------------------------------------------------------
    # 6. AGGREGATOR NODE (UNIFIES ACCUMULATED RESPONSES)
    # -------------------------------------------------------------
    def aggregator_node(state: AgentState):
        responses = state.get("completed_responses") or {}
        if not responses:
            return {"response": "I could not find an answer for your request."}

        # If single intent, return clean raw response without multi-intent headers
        if len(responses) == 1:
            return {"response": next(iter(responses.values()))}

        domain_headers = {
            "product": "🔍 Product Recommendations & Details",
            "order": "📦 Order Details & Tracking",
            "shopping": "🛒 Shopping Cart",
            "support": "ℹ️ Customer Support & Policies",
        }

        sections = []
        for domain, content in responses.items():
            header = domain_headers.get(domain, domain.capitalize())
            sections.append(f"### {header}\n{content.strip()}")

        combined_response = "\n\n---\n\n".join(sections)
        return {"response": combined_response}

    def unknown_node(state: AgentState):
        return {
            "response": (
                "Hello! I am your AI Shopping Assistant. How can I help you today?\n"
                "- Discover products (e.g. 'Show me gaming laptops')\n"
                "- Manage your cart (e.g. 'Show my cart', 'Add Galaxy Pro to cart')\n"
                "- Track and check orders (e.g. 'Show my previous orders', 'Where is my order?')\n"
                "- Customer Support & Policies (e.g. 'What is your return policy?', 'Talk to human')"
            )
        }

    # -------------------------------------------------------------
    # 7. BUILD STATE GRAPH WITH MULTI-INTENT LOOPBACK
    # -------------------------------------------------------------
    builder = StateGraph(AgentState)

    builder.add_node("router", router_node)
    builder.add_node("dispatcher", dispatcher_node)
    builder.add_node("product", product_node)
    builder.add_node("shopping", shopping_node)
    builder.add_node("order", order_node)
    builder.add_node("support", support_node)
    builder.add_node("aggregator", aggregator_node)
    builder.add_node("unknown", unknown_node)

    # Initial flow
    builder.add_edge(START, "router")
    builder.add_edge("router", "dispatcher")

    # Dispatcher to domain agents or aggregator
    builder.add_conditional_edges(
        "dispatcher",
        route_next_intent,
        {
            "product": "product",
            "shopping": "shopping",
            "order": "order",
            "support": "support",
            "aggregator": "aggregator",
            "unknown": "unknown",
        },
    )

    # Domain agents loop back to dispatcher (or pause if awaiting confirmation)
    builder.add_conditional_edges(
        "product",
        should_loop_or_pause,
        {
            "dispatcher": "dispatcher",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "shopping",
        should_loop_or_pause,
        {
            "dispatcher": "dispatcher",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "order",
        should_loop_or_pause,
        {
            "dispatcher": "dispatcher",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "support",
        should_loop_or_pause,
        {
            "dispatcher": "dispatcher",
            END: END,
        },
    )

    # Terminal edges
    builder.add_edge("aggregator", END)
    builder.add_edge("unknown", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)

    if with_checkpointer:
        mem = MemorySaver()
        return builder.compile(checkpointer=mem)

    return builder.compile()
