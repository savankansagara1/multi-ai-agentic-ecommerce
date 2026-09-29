import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END, MessagesState

from app.agents.router import llm
from app.services.product_service import ProductService


class ProductAgentState(MessagesState):
    cart_items: list[dict] | None


def _comparison_search_queries(query: str) -> list[str]:
    parts = re.split(r"\b(?:and|versus|vs)\b", query, flags=re.IGNORECASE)
    return [
        cleaned
        for part in parts
        if (cleaned := re.sub(
            r"^\s*(?:please\s+)?(?:compare|comare)\s+",
            "",
            part,
            flags=re.IGNORECASE,
        ).strip())
    ]


def build_product_graph(db):
    def product_agent_node(state: ProductAgentState):
        messages = state.get("messages", [])
        query = str(messages[-1].content) if messages else ""
        list_all = ProductService.is_catalog_browse_request(query)
        inventory_query = bool(re.search(
            r"\b(?:how many|stock|inventory|availability|available units|units available|in stock)\b",
            query,
            re.IGNORECASE,
        ))
        comparison = bool(re.search(
            r"\b(?:compare|comparison|comare|versus|vs)\b", query, re.IGNORECASE
        ))
        cart_items = state.get("cart_items") or []
        refers_to_cart_product = bool(re.search(
            r"\b(?:that|this|the) product\b|\bproduct\s+(?:i'?m|i am)\s+(?:buying|purchasing)\b|\b(?:in|from) my cart\b",
            query,
            re.IGNORECASE,
        ))
        asks_suitability = bool(re.search(
            r"\b(?:helpful|useful|suitable|good|work)\b.{0,50}\b(?:stud(?:y|ies|ying)|school|college|class|course|coding|work)\b|\b(?:stud(?:y|ies|ying)|school|college|class|course|coding)\b.{0,50}\b(?:helpful|useful|suitable|good|work)\b",
            query,
            re.IGNORECASE,
        ))

        if list_all:
            products = ProductService.list_catalog(db=db)
        elif refers_to_cart_product and cart_items:
            products = []
            for cart_item in cart_items:
                matches = ProductService.search_catalog(
                    db=db,
                    query=f"{cart_item['product_name']} {cart_item['variant_name']}",
                    limit=10,
                    include_out_of_stock=True,
                )
                products.extend(
                    item for item in matches
                    if item["variant_id"] == cart_item.get("product_variant_id")
                )
        elif comparison:
            products = []
            seen = set()
            for part in _comparison_search_queries(query):
                matches = ProductService.search_catalog(
                    db=db, query=part, limit=10, include_out_of_stock=True
                )
                for item in matches:
                    if item["variant_id"] not in seen:
                        seen.add(item["variant_id"])
                        products.append(item)
        else:
            products = ProductService.search_catalog(
                db=db,
                query=query,
                include_out_of_stock=inventory_query,
            )

        # The database is the only source for item details. The LLM writes a
        # conversational response using these rows; canonical rows are appended
        # to preserve exact prices, variants, stock, and complete catalog lists.
        facts = [{
            "product": item["product_name"],
            "variant": item["variant_name"],
            "sku": item.get("sku", ""),
            "price_inr": item["price"],
            "stock": item["stock_quantity"],
            "brand": item.get("brand"),
            "product_specs": item.get("product_specifications", {}),
            "variant_specs": item.get("variant_specifications", {}),
        } for item in products]
        system_prompt = """You are a friendly, conversational e-commerce shopping assistant. Answer the shopper directly and naturally, not with a canned template. Use only the provided catalog data for product facts. Never invent products, specifications, prices, stock, or policies. An empty catalog result means no matching catalog item was found; say that plainly and ask a useful brief follow-up. For comparisons, explain the meaningful differences supported by the data and avoid declaring a universal winner. For a request to see all products, write a short introduction and do not omit or summarize away any catalog items; the exact complete catalog list will follow your response. For stock questions, state the quantity for the relevant variant(s). Keep your conversational text concise. Do not repeat the full catalog rows because they are appended separately."""

        try:
            answer = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=(
                    f"Shopper request: {query}\n"
                    f"Catalog results (authoritative; empty means no match): {json.dumps(facts, ensure_ascii=False)}"
                )),
            ])
            content = str(answer.content).strip()
            if not content:
                raise ValueError("The model returned an empty response")
        except Exception:
            # Operational fallback: retain verified catalog data if the LLM is down.
            content = "Here are the catalog results I could verify:" if products else "I couldn’t retrieve a response just now. Please try again."

        if products:
            content += "\n\n" + "\n".join(
                f"- {item['product_name']} — {item['variant_name']}; "
                f"₹{item['price']:,.2f}; {item['stock_quantity']} in stock; SKU {item.get('sku', 'N/A')}"
                for item in products
            )
        return {"messages": [AIMessage(content=content)]}

    builder = StateGraph(ProductAgentState)
    builder.add_node("agent", product_agent_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()
