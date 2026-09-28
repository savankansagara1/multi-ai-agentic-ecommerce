import re

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState

from app.services.product_service import ProductService


class ProductAgentState(MessagesState):
    pass


def build_product_graph(db):
    def product_agent_node(state: ProductAgentState):
        messages = state.get("messages", [])
        query = str(messages[-1].content) if messages else ""
        list_all = bool(re.search(
            r"\b(?:list|show|display|give)\b.*\b(?:all\s+)?products?\b"
            r"|\bproducts?\s+list\b|\blist\s+of\s+products?\b|\bcatalog\b",
            query,
            re.IGNORECASE,
        ))
        products = (
            ProductService.list_catalog(db=db)
            if list_all
            else ProductService.search_catalog(db=db, query=query)
        )

        if not products:
            content = (
                "I couldn't find an in-stock product in the catalog matching that request. "
                "I haven't included products that aren't in the catalog."
            )
        else:
            budget_match = re.search(
                r"\b(?:under|below|less than|up to|upto|max(?:imum)?)\s*"
                r"(?:₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*(k|thousand)?\b",
                query,
                re.IGNORECASE,
            )
            title = "All active products in the catalog" if list_all else "Catalog matches"
            if budget_match:
                amount = budget_match.group(1).replace(",", "")
                if budget_match.group(2):
                    amount = str(float(amount) * 1000).rstrip("0").rstrip(".")
                title += f" priced at or below ₹{amount}"
            lines = [title + ":"]
            for product in products:
                price = product["price"]
                stock = product["stock_quantity"]
                availability = f"{stock} in stock" if stock > 0 else "currently out of stock"
                name = product["product_name"]
                variant = product["variant_name"]
                sku = product["sku"]
                lines.append(
                    f"- {name} — {variant}; ₹{price:,.2f}; {availability}; SKU {sku}"
                )
            content = "\n".join(lines)

        return {"messages": [AIMessage(content=content)]}

    builder = StateGraph(ProductAgentState)
    builder.add_node("agent", product_agent_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()
