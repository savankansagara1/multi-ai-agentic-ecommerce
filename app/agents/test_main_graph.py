from app.db.database import SessionLocal
from app.agents.day2_conditional_graph import build_main_graph


if __name__ == "__main__":

    db = SessionLocal()

    try:

        graph = build_main_graph(db)

        requests = [
            "Show me products containing Galaxy",
            "Show me laptops under ₹80,000",
            "What is your return policy?",
            ("PRODUCT", "Show me products containing Galaxy"),
            ("SHOPPING", "Show me my cart"),
            ("ORDER", "Show my previous orders"),
            ("ORDER_TRACKING", "Where is order ORD-2026-1001?"),
            ("SUPPORT", "What is your return policy?"),
            ("UNKNOWN", "Hello there"),
        ]

        for request in requests:
        config = {"configurable": {"thread_id": "test-main-graph-session"}}

        for domain, request in requests:
            result = graph.invoke(
                {
                    "message": request
                }
                    "user_id": 1,
                    "message": request,
                },
                config=config,
            )

            print("\n" + "=" * 60)
            print("REQUEST :", request)
            print("INTENT  :", result.get("intent"))
            print(f"[{domain}] REQUEST :", request)
            print("CLASSIFIED INTENT :", result.get("intent"))

            response = result.get("response")

            if hasattr(response, "content"):
                print("RESPONSE:", response.content)
                print("RESPONSE:\n", response.content)
            else:
                print("RESPONSE:", response)
                print("RESPONSE:\n", response)

    finally:
        db.close()