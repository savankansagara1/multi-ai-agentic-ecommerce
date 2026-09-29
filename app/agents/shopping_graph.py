import re
from typing import Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.shopping_agent import create_shopping_agent


def _extract_quantity_from_text(text: str) -> int | None:
    """Helper to detect integer quantities mentioned in user input."""
    match = re.search(r"\b(?:add|put|buy|order|update to|change to|to)\s+(\d+)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d+)\s*(?:x|units?|items?|pieces?)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d+)\s+[a-zA-Z]", text)
    if match:
        return int(match.group(1))

    return None


def _clean_product_query(query: str) -> str:
    """Strip quantity prefixes and noise words from extracted product query."""
    q = re.sub(r"^\d+\s*(?:x\s*)?", "", query, flags=re.IGNORECASE).strip()
    q = re.sub(r"\b(to\s+my\s+cart|in\s+my\s+cart|into\s+cart|to\s+cart|from\s+my\s+cart|from\s+cart)\b", "", q, flags=re.IGNORECASE).strip()
    return q


def build_shopping_graph(db):
    components = create_shopping_agent(db)

    tools = components["tools"]
    view_cart = tools["view_cart"]
    find_product_variants = tools["find_product_variants"]
    add_to_cart = tools["add_to_cart"]
    update_cart_quantity = tools["update_cart_quantity"]
    remove_from_cart = tools["remove_from_cart"]
    clear_cart = tools["clear_cart"]
    checkout = tools["checkout"]

    add_extractor = components["add_extractor"]
    update_extractor = components["update_extractor"]
    remove_extractor = components["remove_extractor"]

    # -------------------------------------------------------------
    # 1. AGENT REASONING NODE
    # -------------------------------------------------------------
    def shopping_agent_node(state: AgentState) -> dict[str, Any]:
        user_id = state.get("user_id", 1)
        raw_message = state.get("message", "").strip()
        message = raw_message.lower()

        # A. Handle existing pending confirmation
        if state.get("awaiting_confirmation") and state.get("pending_action"):
            action = state["pending_action"]

            positive_confirmations = {
                "yes", "y", "confirm", "confirmed", "sure", "proceed",
                "please do", "add it", "checkout", "place order", "ok", "okay", "yes please", "do it"
            }
            negative_confirmations = {
                "no", "n", "cancel", "cancelled", "don't", "dont",
                "stop", "abort", "no thanks", "never mind", "nevermind"
            }

            clean_message = re.sub(r"[^\w\s]", " ", message).strip()
            clean_words = clean_message.split()

            is_positive = (
                any(clean_message == kw or clean_message.startswith(f"{kw} ") for kw in positive_confirmations)
                or ("yes" in clean_words)
                or ("confirm" in clean_words)
                or ("proceed" in clean_words)
            )

            # Positive confirmation: hand off to tools node for execution
            if is_positive:
                return {
                    "action_to_execute": action,
                    "awaiting_confirmation": False,
                }

            # Negative confirmation: cancel action
            is_negative = (
                any(clean_message == kw or clean_message.startswith(f"{kw} ") for kw in negative_confirmations)
                or ("no" in clean_words and "know" not in clean_words)
                or ("cancel" in clean_words and "cancellation" not in clean_words)
                or ("stop" in clean_words)
                or ("dont" in clean_words)
            )
            if is_negative:
                return {
                    "response": "Action cancelled. Your cart remains unchanged.",
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            # Ambiguous confirmation response - re-prompt safely
            action_desc = action.get("summary", "this cart action")
            return {
                "response": (
                    f"Please confirm whether you want to proceed with {action_desc}. "
                    "Reply 'yes' to confirm or 'no' to cancel."
                ),
                "action_to_execute": None,
            }

        # B. Checkout / Place Order intent
        checkout_keywords = ["checkout", "place order", "place the order", "buy now", "complete order", "order my cart"]
        if any(kw in message for kw in checkout_keywords):
            cart = view_cart.invoke({"user_id": user_id})
            if not cart.get("items"):
                return {
                    "response": "Your cart is currently empty. Please add items to your cart before checking out.",
                    "action_to_execute": None,
                }

            items_desc = ", ".join(f"{i['product_name']} x{i['quantity']}" for i in cart["items"])
            total = cart["total"]

            return {
                "pending_action": {
                    "tool": "checkout",
                    "args": {"user_id": user_id},
                    "summary": f"checking out and placing order for {len(cart['items'])} item(s) (Total: ₹{total:,.2f})",
                    "total": total,
                },
                "awaiting_confirmation": True,
                "pending_domain": "shopping",
                "response": (
                    f"You have {len(cart['items'])} item(s) in your cart ({items_desc}) "
                    f"totaling ₹{total:,.2f}. Would you like to proceed and place the order now?"
                ),
                "action_to_execute": None,
            }

        # C. Resolve pending multiple-choice ambiguity
        if state.get("active_options"):
            options = state["active_options"]
            selected_variant = None

            number_words = {"1": 0, "first": 0, "one": 0, "2": 1, "second": 1, "two": 1, "3": 2, "third": 2, "three": 2}
            for word, idx in number_words.items():
                if word in message.split() or message == word:
                    if idx < len(options):
                        selected_variant = options[idx]
                        break

            if not selected_variant:
                for opt in options:
                    if opt["variant_name"].lower() in message or opt["sku"].lower() in message:
                        selected_variant = opt
                        break

            if selected_variant:
                quantity = state.get("pending_quantity") or 1
                return {
                    "active_options": None,
                    "pending_quantity": None,
                    "pending_action": {
                        "tool": "add_to_cart",
                        "args": {
                            "user_id": user_id,
                            "product_variant_id": selected_variant["variant_id"],
                            "quantity": quantity,
                        },
                        "summary": f"adding {quantity} unit(s) of {selected_variant['product_name']} ({selected_variant['variant_name']})",
                        "product_name": selected_variant["product_name"],
                        "variant_name": selected_variant["variant_name"],
                    },
                    "awaiting_confirmation": True,
                    "pending_domain": "shopping",
                    "response": (
                        f"I have selected {selected_variant['product_name']} "
                        f"({selected_variant['variant_name']}) at ₹{selected_variant['price']:,.2f}. "
                        f"Would you like me to add {quantity} item(s) to your cart?"
                    ),
                    "action_to_execute": None,
                }
            else:
                return {
                    "response": "Please choose from the listed options by number (e.g. 1 or 2) or variant name.",
                    "action_to_execute": None,
                }

        # D. Clear Cart intent
        if ("clear" in message and "cart" in message) or message in ["empty my cart", "empty cart", "clear all"]:
            return {
                "pending_action": {
                    "tool": "clear_cart",
                    "args": {"user_id": user_id},
                    "summary": "clearing your entire cart",
                },
                "awaiting_confirmation": True,
                "pending_domain": "shopping",
                "response": "Are you sure you want to clear your entire cart? Reply 'yes' to confirm or 'no' to keep your items.",
                "action_to_execute": None,
            }

        # E. Remove / Delete intent
        remove_words = ["remove", "delete", "discard", "drop"]
        if any(w in message for w in remove_words) and "cart" in message:
            try:
                parsed = remove_extractor.invoke(raw_message)
                product_query = parsed.product_query
            except Exception:
                product_query = raw_message

            cart = view_cart.invoke({"user_id": user_id})
            if not cart["items"]:
                return {
                    "response": "Your cart is currently empty.",
                    "action_to_execute": None,
                }

            matched_item = None
            for item in cart["items"]:
                p_name = item["product_name"].lower()
                v_name = item["variant_name"].lower()
                sku = item["sku"].lower()
                q = product_query.lower()
                if q in p_name or q in v_name or q in sku or any(word in p_name for word in q.split()):
                    matched_item = item
                    break

            if not matched_item:
                return {
                    "response": f"I couldn't find '{product_query}' in your cart. Would you like to view your cart?",
                    "action_to_execute": None,
                }

            return {
                "pending_action": {
                    "tool": "remove_from_cart",
                    "args": {
                        "user_id": user_id,
                        "product_variant_id": matched_item["product_variant_id"],
                    },
                    "summary": f"removing {matched_item['product_name']} ({matched_item['variant_name']}) from your cart",
                    "product_name": matched_item["product_name"],
                    "variant_name": matched_item["variant_name"],
                },
                "awaiting_confirmation": True,
                "pending_domain": "shopping",
                "response": (
                    f"Are you sure you want to remove {matched_item['product_name']} "
                    f"({matched_item['variant_name']}) from your cart? Reply 'yes' to confirm or 'no' to cancel."
                ),
                "action_to_execute": None,
            }

        # F. Update Quantity intent
        update_words = ["change quantity", "update quantity", "change to", "set quantity", "update cart"]
        is_update = any(w in message for w in update_words) or (re.search(r"\b(?:change|update|set)\b.*\b(?:to|\d+)\b", message))
        if is_update and ("cart" in message or "item" in message or "quantity" in message):
            extracted_qty = _extract_quantity_from_text(raw_message)
            try:
                parsed = update_extractor.invoke(raw_message)
                product_query = parsed.product_query
                quantity = extracted_qty if extracted_qty is not None else parsed.quantity
            except Exception:
                product_query = raw_message
                quantity = extracted_qty if extracted_qty is not None else 1

            cart = view_cart.invoke({"user_id": user_id})
            if not cart["items"]:
                return {
                    "response": "Your cart is currently empty.",
                    "action_to_execute": None,
                }

            matched_item = None
            for item in cart["items"]:
                p_name = item["product_name"].lower()
                v_name = item["variant_name"].lower()
                sku = item["sku"].lower()
                q = product_query.lower()
                if q in p_name or q in v_name or q in sku or any(word in p_name for word in q.split()):
                    matched_item = item
                    break

            if not matched_item:
                return {
                    "response": f"I couldn't find '{product_query}' in your cart.",
                    "action_to_execute": None,
                }

            return {
                "pending_action": {
                    "tool": "update_cart_quantity",
                    "args": {
                        "user_id": user_id,
                        "product_variant_id": matched_item["product_variant_id"],
                        "quantity": quantity,
                    },
                    "summary": f"updating {matched_item['product_name']} ({matched_item['variant_name']}) quantity to {quantity}",
                    "product_name": matched_item["product_name"],
                    "variant_name": matched_item["variant_name"],
                },
                "awaiting_confirmation": True,
                "pending_domain": "shopping",
                "response": (
                    f"Would you like to update {matched_item['product_name']} "
                    f"({matched_item['variant_name']}) quantity from {matched_item['quantity']} to {quantity}?"
                ),
                "action_to_execute": None,
            }

        # G. Add to Cart intent
        add_keywords = ["add", "buy", "put", "cart"]
        is_add_intent = any(re.search(rf"\b{kw}\b", message) for kw in ["add", "put in cart", "add to cart", "buy"])
        if is_add_intent and not any(kw in message for kw in ["view", "show", "what is in", "contents", "clear", "remove", "delete"]):
            extracted_qty = _extract_quantity_from_text(raw_message)
            try:
                parsed = add_extractor.invoke(raw_message)
                product_query = parsed.product_query
                quantity = extracted_qty if extracted_qty is not None else parsed.quantity
            except Exception:
                quantity = extracted_qty if extracted_qty is not None else 1
                match = re.search(r"\b(?:add|buy|put)\s+(.+?)(?:\s+to\s+my\s+cart|\s+to\s+cart|$)", raw_message, re.IGNORECASE)
                product_query = match.group(1).strip() if match else raw_message

            product_query = _clean_product_query(product_query)

            if not product_query:
                return {
                    "response": "Please specify which product you would like to add to your cart.",
                    "action_to_execute": None,
                }

            variants = find_product_variants.invoke({
                "query": product_query,
                "limit": 5,
            })

            if not variants:
                return {
                    "response": f"I couldn't find a product matching '{product_query}'.",
                    "action_to_execute": None,
                }

            if len(variants) > 1:
                options = []
                for index, v in enumerate(variants, start=1):
                    options.append(
                        f"{index}. {v['product_name']} ({v['variant_name']}) - ₹{v['price']:,.2f}"
                    )

                return {
                    "active_options": variants,
                    "pending_quantity": quantity,
                    "response": (
                        f"I found multiple options for '{product_query}'. Which one would you like?\n"
                        + "\n".join(options)
                    ),
                    "action_to_execute": None,
                }

            variant = variants[0]
            if variant["stock_quantity"] < quantity:
                return {
                    "response": (
                        f"Only {variant['stock_quantity']} unit(s) are currently in stock for "
                        f"{variant['product_name']} ({variant['variant_name']})."
                    ),
                    "action_to_execute": None,
                }

            return {
                "pending_action": {
                    "tool": "add_to_cart",
                    "args": {
                        "user_id": user_id,
                        "product_variant_id": variant["variant_id"],
                        "quantity": quantity,
                    },
                    "summary": f"adding {quantity} unit(s) of {variant['product_name']} ({variant['variant_name']})",
                    "product_name": variant["product_name"],
                    "variant_name": variant["variant_name"],
                },
                "awaiting_confirmation": True,
                "pending_domain": "shopping",
                "response": (
                    f"I found {variant['product_name']} ({variant['variant_name']}) at "
                    f"₹{variant['price']:,.2f}. Would you like me to add {quantity} item(s) to your cart?"
                ),
                "action_to_execute": None,
            }

        # H. View Cart intent (executes tool)
        view_keywords = ["view cart", "show my cart", "show me my cart", "what's in my cart", "what is in my cart", "cart contents", "see my cart", "check my cart"]
        is_view_intent = (
            any(kw in message for kw in view_keywords)
            or message in ["cart", "my cart"]
            or ("cart" in message and re.search(r"\b(status|current|contents|items|what is|what's|show|view|check|see)\b", message))
        )

        if is_view_intent:
            return {
                "action_to_execute": {
                    "tool": "view_cart",
                    "args": {"user_id": user_id},
                }
            }

        # Fallback
        return {
            "response": (
                "I can help you view your cart, add products, update quantities, "
                "or remove items. What would you like to do?"
            ),
            "action_to_execute": None,
        }

    # -------------------------------------------------------------
    # 2. TOOLS EXECUTION NODE
    # -------------------------------------------------------------
    def shopping_tools_node(state: AgentState) -> dict[str, Any]:
        action = state.get("action_to_execute")
        if not action:
            return state

        tool_name = action.get("tool")
        args = action.get("args", {})

        try:
            if tool_name == "view_cart":
                cart = view_cart.invoke(args)
                if not cart["items"]:
                    return {
                        "response": "Your cart is currently empty.",
                        "cart_items": [],
                        "action_to_execute": None,
                    }

                lines = ["Your shopping cart:"]
                for idx, item in enumerate(cart["items"], start=1):
                    lines.append(
                        f"{idx}. {item['product_name']} ({item['variant_name']}) - "
                        f"{item['quantity']} × ₹{item['unit_price']:,.2f} = ₹{item['line_total']:,.2f}"
                    )
                lines.append(f"\nTotal: ₹{cart['total']:,.2f} ({cart['item_count']} item(s))")

                return {
                    "response": "\n".join(lines),
                    "cart_items": cart["items"],
                    "action_to_execute": None,
                }

            elif tool_name == "add_to_cart":
                result = add_to_cart.invoke(args)
                p_name = action.get("product_name", "product")
                v_name = action.get("variant_name", "")
                return {
                    "response": (
                        f"Added {result['quantity']} unit(s) of {p_name} "
                        f"({v_name}) to your cart successfully."
                    ),
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "update_cart_quantity":
                result = update_cart_quantity.invoke(args)
                p_name = action.get("product_name", "item")
                v_name = action.get("variant_name", "")
                return {
                    "response": (
                        f"Updated {p_name} ({v_name}) quantity to "
                        f"{result['new_quantity']} in your cart."
                    ),
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "remove_from_cart":
                result = remove_from_cart.invoke(args)
                return {
                    "response": result["message"],
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "clear_cart":
                result = clear_cart.invoke(args)
                return {
                    "response": result["message"],
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

            elif tool_name == "checkout":
                result = checkout.invoke(args)
                return {
                    "response": (
                        f"Order {result['order_number']} placed successfully! "
                        f"Total: ₹{result['total_amount']:,.2f}. "
                        f"Tracking Number: {result['tracking_number']}. "
                        f"Estimated Delivery: {result['estimated_delivery']}."
                    ),
                    "pending_action": None,
                    "awaiting_confirmation": False,
                    "pending_domain": None,
                    "action_to_execute": None,
                }

        except Exception as e:
            return {
                "response": f"Failed to execute operation: {str(e)}",
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
    # 4. BUILD SHOPPING AGENT GRAPH (AGENT <-> TOOLS)
    # -------------------------------------------------------------
    builder = StateGraph(AgentState)
    builder.add_node("agent", shopping_agent_node)
    builder.add_node("tools", shopping_tools_node)

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

    return builder.compile()
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)