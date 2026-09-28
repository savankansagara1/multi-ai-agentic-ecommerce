from app.agents.orchestrator import build_main_graph
from app.db.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        graph = build_main_graph(db)
        requests = [
            "Show me products containing Galaxy",
            "Show me my cart",
            "What is your return policy?",
        ]
        for index, message in enumerate(requests, start=1):
            result = graph.invoke(
                {"user_id": 1, "message": message},
                config={"configurable": {"thread_id": f"demo-{index}"}},
            )
            print(f"\nUSER: {message}\nASSISTANT: {result.get('response', '')}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
