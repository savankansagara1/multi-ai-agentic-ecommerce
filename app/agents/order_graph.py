import re
from typing import Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.order_agent import create_order_agent


def _extract_order_identifier(text: str) -> str | None:
    """Extract order numbers like 'ORD-2026-1001' or numeric order IDs from text."""
    match = re.search(r"\bORD-[0-9A-Za-z-]+\b", text, re.IGNORECASE)
    if match:
        return match.group(0).upper()

    match = re.search(r"\border\s*(?:#|number|id)?\s*([0-9]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def build_order_graph(db):
    components = create_order_agent(db)

    tools = components["tools"]
    get_user_orders = tools["get_user_orders"]
    get_order_details = tools["get_order_details"]
    get_order_status = tools["get_order_status"]
    get_shipment_status = tools["get_shipment_status"]
    cancel_order = tools["cancel_order"]
    request_return = tools["request_return"]

    # -------------------------------------------------------------
    # 1. AGENT REASONING NODE
    # -------------------------------------------------------------
    def order_agent_node(state: AgentState) -> dict[str, Any]:
        user_id = state.get("user_id", 1)
        raw_message = state.get("message", "").strip()
        message = raw_message.lower()

        # ---------------------------------------------------------
        # A. Handle existing pending confirmation
        # ---------------------------------------------------------
        if state.get("awaiting_confirmation") and state.get("pending_action"):
            action = state["pending_action"]

            positive_confirmations = {
                "yes", "y", "confirm", "confirmed", "sure", "proceed",
                "please do", "cancel it", "return it", "ok", "okay", "yes please", "do it"
            }
            negative_confirmations = {
                "no", "n", "keep", "keep order", "don't", "dont",
                "stop", "abort", "no thanks", "never mind", "nevermind"
            }

            clean_message = re.sub(r"[^\w\s]", " ", message).strip()
            clean_words = clean_message.split()

            is_positive = (
                any(message == kw or message.startswith(f"{kw} ") or clean_message.startswith(f"{kw} ") for kw in positive_confirmations)
                or ("yes" in clean_words)
                or ("confirm" in clean_words)
                or ("proceed" in clean_words)
            )

            if is_positive:
                return {
                    "action_to_execute": action,
                    "awaiting_confirmation": False,
                }

            is_negative = (
                any(message == kw or message.startswith(f"{kw} ") for kw in negative_confirmations)
                or ("no" in clean_words and "know" not in clean_words)
                or ("dont" in clean_words)
                or ("stop" in clean_words)
            )

            if is_negative:
                order_num = action.get("order_number", "your order")
                action_type = "Cancellation" if action.get("tool") == "cancel_order" else "Return"
                return {
                    "response": f"{action_type} request cancelled. Order {order_num} remains unchanged.",
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            action_desc = action.get("summary", "this order action")
            return {
                "response": (
                    f"Please confirm whether you want to proceed with {action_desc}. "
                    "Reply 'yes' to confirm or 'no' to keep your order unchanged."
                ),
                "awaiting_confirmation": True,
                "pending_action": action,
                "action_to_execute": None,
            }

        # ---------------------------------------------------------
        # B. Cancel Order intent
        # ---------------------------------------------------------
        if "cancel" in message and ("order" in message or re.search(r"ORD-", raw_message, re.I)):
            identifier = _extract_order_identifier(raw_message)

            if not identifier:
                recent_orders = get_user_orders.invoke({"user_id": user_id, "limit": 3})
                cancellable = [o for o in recent_orders if o["status"] in ["placed", "pending", "processing"]]
                if not cancellable:
                    return {
                        "response": "You don't have any pending orders eligible for cancellation.",
                        "action_to_execute": None,
                    }
                identifier = cancellable[0]["order_number"]

            order = get_order_details.invoke({"user_id": user_id, "order_identifier": identifier})
            if not order:
                return {
                    "response": f"I couldn't find order '{identifier}' associated with your account.",
                    "action_to_execute": None,
                }

            if order["status"] in ["cancelled", "canceled"]:
                return {
                    "response": f"Order {order['order_number']} is already cancelled.",
                    "action_to_execute": None,
                }

            if order["status"] in ["shipped", "delivered"]:
                return {
                    "response": (
                        f"Order {order['order_number']} cannot be cancelled because it is already {order['status']}. "
                        "You can request a return after delivery."
                    ),
                    "action_to_execute": None,
                }

            return {
                "pending_action": {
                    "tool": "cancel_order",
                    "args": {
                        "user_id": user_id,
                        "order_identifier": order["order_number"],
                        "reason": "Customer requested cancellation via assistant",
                    },
                    "summary": f"cancelling order {order['order_number']}",
                    "order_number": order["order_number"],
                },
                "awaiting_confirmation": True,
                "pending_domain": "order",
                "response": (
                    f"Are you sure you want to cancel order {order['order_number']} "
                    f"(Total: ₹{order['total_amount']:,.2f})? "
                    "Reply 'yes' to confirm or 'no' to keep your order."
                ),
                "action_to_execute": None,
            }

        # ---------------------------------------------------------
        # C. Return / Refund Order intent
        # ---------------------------------------------------------
        if ("return" in message or "refund" in message) and not ("policy" in message or "how to return" in message or "what is" in message):
            identifier = _extract_order_identifier(raw_message)

            if not identifier:
                recent_orders = get_user_orders.invoke({"user_id": user_id, "limit": 5})
                delivered = [o for o in recent_orders if o["status"] == "delivered"]
                if not delivered:
                    return {
                        "response": "You don't have any delivered orders eligible for return.",
                        "action_to_execute": None,
                    }
                identifier = delivered[0]["order_number"]

            order = get_order_details.invoke({"user_id": user_id, "order_identifier": identifier})
            if not order:
                return {
                    "response": f"I couldn't find order '{identifier}' associated with your account.",
                    "action_to_execute": None,
                }

            if order["status"] != "delivered":
                return {
                    "response": (
                        f"Order {order['order_number']} is currently '{order['status']}'. "
                        "Only delivered orders can be returned. You can request a return after delivery."
                    ),
                    "action_to_execute": None,
                }

            if order.get("returns"):
                return {
                    "response": f"A return request has already been recorded for order {order['order_number']}.",
                    "action_to_execute": None,
                }

            return {
                "pending_action": {
                    "tool": "request_return",
                    "args": {
                        "user_id": user_id,
                        "order_identifier": order["order_number"],
                        "reason": "Customer requested return via assistant",
                    },
                    "summary": f"requesting a return and refund for order {order['order_number']}",
                    "order_number": order["order_number"],
                },
                "awaiting_confirmation": True,
                "pending_domain": "order",
                "response": (
                    f"Are you sure you want to request a return and refund for order {order['order_number']} "
                    f"(Total: ₹{order['total_amount']:,.2f})? "
                    "Reply 'yes' to submit the return request or 'no' to keep your items."
                ),
                "action_to_execute": None,
            }

        # ---------------------------------------------------------
        # D. Shipment Tracking / Delivery Status
        # ---------------------------------------------------------
        tracking_keywords = ["track", "tracking", "shipment", "delivery", "delivered", "where is", "when will"]
        if any(kw in message for kw in tracking_keywords):
            identifier = _extract_order_identifier(raw_message)

            if not identifier:
                recent = get_user_orders.invoke({"user_id": user_id, "limit": 1})
                if not recent:
                    return {
                        "response": "You don't have any past orders to track.",
                        "action_to_execute": None,
                    }
                identifier = recent[0]["order_number"]

            return {
                "action_to_execute": {
                    "tool": "get_shipment_status",
                    "args": {
                        "user_id": user_id,
                        "order_identifier": identifier,
                    },
                }
            }

        # ---------------------------------------------------------
        # E. Order Status
        # ---------------------------------------------------------
        status_keywords = ["status", "check order", "order update"]
        if any(kw in message for kw in status_keywords):
            identifier = _extract_order_identifier(raw_message)

            if not identifier:
                recent = get_user_orders.invoke({"user_id": user_id, "limit": 1})
                if not recent:
                    return {
                        "response": "You don't have any recent orders to check.",
                        "action_to_execute": None,
                    }
                identifier = recent[0]["order_number"]

            return {
                "action_to_execute": {
                    "tool": "get_order_status",
                    "args": {
                        "user_id": user_id,
                        "order_identifier": identifier,
                    },
                }
            }

        # ---------------------------------------------------------
        # F. Order Details
        # ---------------------------------------------------------
        detail_keywords = ["detail", "order info", "order information", "what did i order"]
        identifier = _extract_order_identifier(raw_message)
        if identifier or any(kw in message for kw in detail_keywords):
            if not identifier:
                recent = get_user_orders.invoke({"user_id": user_id, "limit": 1})
                if not recent:
                    return {
                        "response": "You have no past orders.",
                        "action_to_execute": None,
                    }
                identifier = recent[0]["order_number"]

            return {
                "action_to_execute": {
                    "tool": "get_order_details",
                    "args": {
                        "user_id": user_id,
                        "order_identifier": identifier,
                    },
                }
            }

        # ---------------------------------------------------------
        # G. View Recent Orders / History
        # ---------------------------------------------------------
        return {
            "action_to_execute": {
                "tool": "get_user_orders",
                "args": {
                    "user_id": user_id,
                    "limit": 5,
                },
            }
        }

    # -------------------------------------------------------------
    # 2. TOOLS EXECUTION NODE
    # -------------------------------------------------------------
    def order_tools_node(state: AgentState) -> dict[str, Any]:
        action = state.get("action_to_execute")
        if not action:
            return state

        tool_name = action.get("tool")
        args = action.get("args", {})

        try:
            if tool_name == "cancel_order":
                result = cancel_order.invoke(args)
                return {
                    "response": f"Order {result['order_number']} has been successfully cancelled.",
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "request_return":
                result = request_return.invoke(args)
                return {
                    "response": (
                        f"Return request for order {result['order_number']} has been submitted successfully. "
                        f"A refund of ₹{result['refund_amount']:,.2f} will be credited to your original payment method within 5-7 business days."
                    ),
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "get_shipment_status":
                shipment = get_shipment_status.invoke(args)
                if not shipment:
                    return {
                        "response": f"I couldn't find shipment information for order '{args.get('order_identifier')}' in your account.",
                        "action_to_execute": None,
                    }

                if shipment.get("status") == "pending_shipment":
                    return {
                        "response": f"Order {shipment['order_number']} is being prepared and has not shipped yet.",
                        "action_to_execute": None,
                    }

                lines = [f"Tracking information for order {shipment['order_number']}:"]
                lines.append(f"- Status: {shipment['status'].replace('_', ' ').title()}")
                if shipment.get("carrier"):
                    lines.append(f"- Carrier: {shipment['carrier']}")
                if shipment.get("tracking_number"):
                    lines.append(f"- Tracking Number: {shipment['tracking_number']}")
                if shipment.get("shipped_at"):
                    lines.append(f"- Dispatched: {shipment['shipped_at']}")
                if shipment.get("estimated_delivery_at"):
                    lines.append(f"- Estimated Delivery: {shipment['estimated_delivery_at']}")
                if shipment.get("delivered_at"):
                    lines.append(f"- Delivered On: {shipment['delivered_at']}")

                return {
                    "response": "\n".join(lines),
                    "action_to_execute": None,
                }

            elif tool_name == "get_order_status":
                status_res = get_order_status.invoke(args)
                if not status_res:
                    return {
                        "response": f"I couldn't find an order matching '{args.get('order_identifier')}' in your account.",
                        "action_to_execute": None,
                    }

                return {
                    "response": (
                        f"Order {status_res['order_number']} is currently {status_res['status'].upper()}.\n"
                        f"- Total Amount: ₹{status_res['total_amount']:,.2f}\n"
                        f"- Items: {status_res['item_count']} item(s)\n"
                        f"- Shipment Status: {status_res['shipment_status']}\n"
                        f"- Placed On: {status_res['created_at']}"
                    ),
                    "action_to_execute": None,
                }

            elif tool_name == "get_order_details":
                order = get_order_details.invoke(args)
                if not order:
                    return {
                        "response": f"I couldn't find order '{args.get('order_identifier')}' associated with your account.",
                        "action_to_execute": None,
                    }

                lines = [
                    f"Order {order['order_number']} Details:",
                    f"- Status: {order['status'].upper()}",
                    f"- Placed: {order['created_at']}",
                    f"- Total: ₹{order['total_amount']:,.2f}",
                    "\nItems:",
                ]
                for item in order["items"]:
                    lines.append(
                        f"  • {item['product_name']} × {item['quantity']} @ ₹{item['unit_price']:,.2f}"
                    )

                if order.get("payments"):
                    p = order["payments"][0]
                    lines.append(f"\nPayment: {p['payment_method']} ({p['status'].upper()})")

                if order.get("shipments"):
                    s = order["shipments"][-1]
                    lines.append(f"Shipment: {s['carrier']} ({s['status']}) - Tracking: {s['tracking_number']}")

                return {
                    "response": "\n".join(lines),
                    "action_to_execute": None,
                }

            elif tool_name == "get_user_orders":
                orders = get_user_orders.invoke(args)
                if not orders:
                    return {
                        "response": "You haven't placed any orders yet.",
                        "action_to_execute": None,
                    }

                lines = ["Here are your recent orders:"]
                for idx, o in enumerate(orders, start=1):
                    lines.append(
                        f"{idx}. Order {o['order_number']} - {o['status'].upper()}\n"
                        f"   Items: {o['items_summary']}\n"
                        f"   Total: ₹{o['total_amount']:,.2f} | Placed: {o['created_at']}"
                    )

                return {
                    "response": "\n\n".join(lines),
                    "action_to_execute": None,
                }

        except Exception as e:
            return {
                "response": f"Failed to process order action: {str(e)}",
                "pending_action": None,
                "awaiting_confirmation": False,
                "pending_domain": None,
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
    # 4. BUILD ORDER AGENT GRAPH (AGENT <-> TOOLS)
    # -------------------------------------------------------------
    builder = StateGraph(AgentState)
    builder.add_node("agent", order_agent_node)
    builder.add_node("tools", order_tools_node)

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

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
