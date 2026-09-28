from app.agents.order_graph import build_order_graph
from app.db.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        graph = build_order_graph(db)
        result = graph.invoke({"message": "Show my previous orders", "user_id": 1})
        print(result.get("response", "No response returned"))
    finally:
        db.close()


if __name__ == "__main__":
    main()
