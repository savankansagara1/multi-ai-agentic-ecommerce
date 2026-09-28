from app.agents.router import classify_intent


if __name__ == "__main__":
    requests = [
        "Show me laptops under ₹80,000",
        "Add the second laptop to my cart",
        "Show me my previous order",
        "My order hasn't arrived yet",
        "What is your return policy?",
    ]

    for request in requests:
        result = classify_intent(request)

        print("\nREQUEST:", request)
        print("INTENT:", result.intent.value)