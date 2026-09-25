import re
from typing import Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.support_agent import create_support_agent


def build_support_graph(db, with_checkpointer: bool = False):
    components = create_support_agent(db)
    llm = components["llm"]
    tools = components["tools"]
    search_knowledge_base = tools["search_knowledge_base"]
    escalate_to_human = tools["escalate_to_human"]

    # -------------------------------------------------------------
    # 1. AGENT REASONING NODE
    # -------------------------------------------------------------
    def support_agent_node(state: AgentState) -> dict[str, Any]:
        user_id = state.get("user_id", 1)
        raw_message = state.get("message", "").strip()
        message = raw_message.lower()

        # ---------------------------------------------------------
        # A. Detect Explicit Human Escalation Request
        # ---------------------------------------------------------
        escalate_keywords = [
            "escalate", "human", "representative", "agent", "executive",
            "talk to person", "speak to someone", "file a complaint",
            "unresolved", "supervisor", "manager", "dispute"
        ]
        if any(kw in message for kw in escalate_keywords) and not ("what is" in message and "escalation" in message):
            return {
                "action_to_execute": {
                    "tool": "escalate_to_human",
                    "args": {
                        "user_id": user_id,
                        "issue_description": raw_message,
                        "reason": "Direct user request for human specialist",
                    },
                }
            }

        # ---------------------------------------------------------
        # B. Policy / Knowledge Base Search Query
        # ---------------------------------------------------------
        if raw_message:
            return {
                "action_to_execute": {
                    "tool": "search_knowledge_base",
                    "args": {
                        "query": raw_message,
                        "limit": 3,
                    },
                }
            }

        # ---------------------------------------------------------
        # C. Fallback General Support Response
        # ---------------------------------------------------------
        return {
            "response": (
                "Customer Support Assistance:\n"
                "- Returns & Refunds: Eligible items can be returned within 7 days of delivery.\n"
                "- Shipping: Free standard shipping on orders above ₹499; delivery within 2-4 business days.\n"
                "- Warranty: 1-year manufacturer warranty on laptops and smartphones.\n\n"
                "Would you like me to connect you with a human support specialist?"
            ),
            "action_to_execute": None,
        }

    # -------------------------------------------------------------
    # 2. TOOLS EXECUTION NODE
    # -------------------------------------------------------------
    def support_tools_node(state: AgentState) -> dict[str, Any]:
        action = state.get("action_to_execute")
        if not action:
            return state

        tool_name = action.get("tool")
        args = action.get("args", {})
        raw_message = state.get("message", "").strip()

        try:
            if tool_name == "escalate_to_human":
                result = escalate_to_human.invoke(args)
                return {
                    "response": (
                        f"{result['message']}\n\n"
                        f"**Ticket ID:** `{result['ticket_id']}`\n"
                        f"**Status:** {result['status'].capitalize()}\n"
                        f"**Follow-up:** {result['contact_window']}"
                    ),
                    "action_to_execute": None,
                }

            elif tool_name == "search_knowledge_base":
                chunks = search_knowledge_base.invoke(args)
                if chunks:
                    context_blocks = []
                    for chunk in chunks:
                        context_blocks.append(
                            f"Source [{chunk['document_file']}] (Topic: {chunk['topic']}):\n{chunk['content']}"
                        )
                    context_str = "\n\n".join(context_blocks)

                    system_prompt = (
                        "You are an expert, courteous e-commerce customer support specialist. "
                        "Answer the customer's question thoroughly and accurately based ONLY on the provided context below. "
                        "Do NOT make up facts, timelines, or warranty terms. "
                        "Be polite, professional, and clear. Format key details with bullet points where helpful. "
                        "If the context does not contain sufficient details to address the user's issue, provide the best available info and offer human escalation.\n\n"
                        f"RELEVANT KNOWLEDGE BASE CONTEXT:\n{context_str}"
                    )

                    try:
                        ai_response = llm.invoke([
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=raw_message),
                        ])
                        answer = ai_response.content if hasattr(ai_response, "content") else str(ai_response)
                        return {
                            "response": answer,
                            "action_to_execute": None,
                        }
                    except Exception:
                        bullets = "\n".join(f"- {c['content']}" for c in chunks)
                        return {
                            "response": (
                                f"Here is the relevant support information:\n\n{bullets}\n\n"
                                "If you need further assistance, please let me know and I can escalate your request to a specialist."
                            ),
                            "action_to_execute": None,
                        }

                return {
                    "response": (
                        "Customer Support Assistance:\n"
                        "- Returns & Refunds: Eligible items can be returned within 7 days of delivery.\n"
                        "- Shipping: Free standard shipping on orders above ₹499; delivery within 2-4 business days.\n"
                        "- Warranty: 1-year manufacturer warranty on laptops and smartphones.\n\n"
                        "Would you like me to connect you with a human support specialist?"
                    ),
                    "action_to_execute": None,
                }

        except Exception as e:
            return {
                "response": f"Support assistance error: {str(e)}",
                "action_to_execute": None,
            }

        return {"action_to_execute": None}

    # -------------------------------------------------------------
    # 3. CONDITIONAL ROUTING FUNCTION
    # -------------------------------------------------------------
    def should_call_tools(state: AgentState):
        if state.get("action_to_execute"):
            return "tools"
        return END

    # -------------------------------------------------------------
    # 4. BUILD SUPPORT AGENT GRAPH (AGENT <-> TOOLS)
    # -------------------------------------------------------------
    builder = StateGraph(AgentState)
    builder.add_node("agent", support_agent_node)
    builder.add_node("tools", support_tools_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        should_call_tools,
        {
            "tools": "tools",
            END: END,
        }
    )
    builder.add_edge("tools", END)

    if with_checkpointer:
        checkpointer = MemorySaver()
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
