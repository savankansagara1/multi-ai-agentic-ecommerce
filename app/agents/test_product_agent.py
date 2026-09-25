from app.db.database import SessionLocal
from app.agents.product_agent import create_product_agent


if __name__ == "__main__":
    db = SessionLocal()

    try:
        llm, tools = create_product_agent(db)

        message = "Show me products containing Galaxy"

        response = llm.invoke(message)

        print("\nLLM RESPONSE:")
        print(response)

        print("\nTOOL CALLS:")
        for tool_call in response.tool_calls:
            print(tool_call)

    finally:
        db.close()