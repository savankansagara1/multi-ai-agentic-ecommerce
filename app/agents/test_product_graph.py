from app.db.database import SessionLocal
from app.agents.product_graph import build_product_graph


if __name__ == "__main__":
    db = SessionLocal()

    try:
        graph = build_product_graph(db)

        result = graph.invoke({
            "message": "Show me products containing Galaxy"
        })

        print("\nFINAL RESPONSE:")
        print(result["response"].content)

    finally:
        db.close()