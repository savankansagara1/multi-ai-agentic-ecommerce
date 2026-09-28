from app.db.database import SessionLocal
from app.agents.shopping_agent import create_shopping_agent


if __name__ == "__main__":
    db = SessionLocal()

    try:
        llm, tools = create_shopping_agent(db)

        requests = [
            "Add Galaxy Buds to my cart",
            "Add 2 Galaxy Buds to my cart",
            "Put three Galaxy Buds in my cart",
        ]

        for request in requests:
            result = llm.invoke(request)

            print("\nREQUEST:")
            print(request)

            print("PRODUCT:")
            print(result.product_query)

            print("QUANTITY:")
            print(result.quantity)

    finally:
        db.close()