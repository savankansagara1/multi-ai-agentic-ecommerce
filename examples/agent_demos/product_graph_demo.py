from app.agents.product_graph import build_product_graph
from app.db.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        graph = build_product_graph(db)
        result = graph.invoke({"messages": [{"role": "user", "content": "Show me products containing Galaxy"}]})
        print(result["messages"][-1].content)
    finally:
        db.close()


if __name__ == "__main__":
    main()
