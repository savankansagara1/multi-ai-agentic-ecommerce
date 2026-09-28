from app.db.database import SessionLocal
from app.agents.shopping_graph import build_shopping_graph


if __name__ == "__main__":
    db = SessionLocal()

    try:
        graph = build_shopping_graph(db)
        config = {
            "configurable": {
                "thread_id": "shopping-demo-session-1"
            }
        }

        # ---------------------------------------------------------
        # STEP 1: VIEW CART
        # ---------------------------------------------------------
        result = graph.invoke(
            {
                "user_id": 1,
                "message": "Show me my cart",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 1: VIEW CART")
        print("=" * 60)
        print(result["response"])

        # ---------------------------------------------------------
        # STEP 2: ADD PRODUCT WITH AMBIGUITY (MULTIPLE VARIANTS)
        # ---------------------------------------------------------
        result = graph.invoke(
            {
                "user_id": 1,
                "message": "Add ThinkBook Pro to my cart",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 2: ADD PRODUCT WITH MULTIPLE VARIANTS")
        print("=" * 60)
        print(result["response"])
        print("Active Options:", len(result.get("active_options") or []))

        # ---------------------------------------------------------
        # STEP 3: RESOLVE AMBIGUITY (SELECT OPTION 1)
        # ---------------------------------------------------------
        result = graph.invoke(
            {
                "user_id": 1,
                "message": "1",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 3: USER SELECTS OPTION 1 (CONFIRMATION PROMPT)")
        print("=" * 60)
        print(result["response"])
        print("Pending Action:", result.get("pending_action"))
        print("Awaiting Confirmation:", result.get("awaiting_confirmation"))

        # ---------------------------------------------------------
        # STEP 4: CONFIRM TRANSACTION ("yes")
        # ---------------------------------------------------------
        result = graph.invoke(
            {
                "user_id": 1,
                "message": "yes",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 4: USER CONFIRMS (MUTATION EXECUTED)")
        print("=" * 60)
        print(result["response"])
        print("Pending Action:", result.get("pending_action"))
        print("Awaiting Confirmation:", result.get("awaiting_confirmation"))

        # ---------------------------------------------------------
        # STEP 5: CANCEL TRANSACTION DEMO ("no")
        # ---------------------------------------------------------
        result = graph.invoke(
            {
                "user_id": 1,
                "message": "Remove ThinkBook from my cart",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 5: SENSITIVE REMOVE REQUEST")
        print("=" * 60)
        print(result["response"])
        print("Pending Action:", result.get("pending_action"))

        result = graph.invoke(
            {
                "user_id": 1,
                "message": "no",
            },
            config=config,
        )
        print("\n" + "=" * 60)
        print("STEP 6: USER CANCELS REMOVAL")
        print("=" * 60)
        print(result["response"])
        print("Pending Action:", result.get("pending_action"))

    finally:
        db.close()