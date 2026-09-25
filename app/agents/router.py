import re
from enum import Enum
from dotenv import load_dotenv

from langchain_ollama import ChatOllama

from app.schemas.agent import Intent, IntentClassification

load_dotenv()


llm = ChatOllama(
    model="gpt-oss:120b-cloud",
    temperature=0,
)


def detect_intents(message: str) -> list[str]:
    """Detect if a user message contains multiple distinct intents (compound requests)."""
    m = message.lower()
    intents = []

    # Check for shopping keywords
    shopping_patterns = [
        r"\b(?:view\s+cart|show\s+cart|my\s+cart|see\s+cart|in\s+my\s+cart|checkout|place\s+order|buy\s+now|clear\s+cart)\b",
        r"\b(?:add|remove|delete|update)\b.*\b(?:cart)\b",
    ]
    if any(re.search(p, m) for p in shopping_patterns):
        intents.append("shopping")

    # Check for support / policy keywords
    support_patterns = [
        r"\b(?:return\s+policy|refund\s+policy|cancellation\s+policy|shipping\s+policy|warranty|guarantee|troubleshoot|human\s+agent|speak\s+with|talk\s+to\s+human|customer\s+care|support\s+hours|help\s+desk|policy)\b",
    ]
    if any(re.search(p, m) for p in support_patterns):
        intents.append("support")

    # Check for order keywords (specific to existing user orders)
    order_patterns = [
        r"\b(?:my\s+orders?|previous\s+orders?|past\s+orders?|order\s+status|track\s+order|where\s+is\s+my\s+order|cancel\s+order|return\s+order)\b",
        r"\bORD-[0-9A-Za-z-]+\b",
    ]
    if any(re.search(p, m) for p in order_patterns):
        if not ("support" in intents and not any(re.search(p, m) for p in [r"\bmy\s+order", r"\bord-"])):
            intents.append("order")

    # Check for product discovery keywords
    product_patterns = [
        r"\b(?:specs|specifications|features|compare|processor|display|best\s+camera|laptop\s+under|phone\s+under)\b",
    ]
    if any(re.search(p, m) for p in product_patterns) and "shopping" not in intents:
        intents.append("product")

    # If compound intent detected (2 or more distinct domains)
    if len(intents) >= 2:
        return list(dict.fromkeys(intents))

    # Single domain or ambiguous: rely on LLM classification
    single = classify_intent(message)
    return [single.intent.value]


def classify_intent(message: str) -> IntentClassification:

    prompt = f"""
You are an intent classifier for an e-commerce AI assistant.

Classify the user's request into EXACTLY ONE of these values:

product
shopping
order
support
unknown

Definitions:

product:
- product search
- product information
- product comparison
- product recommendations
- product availability
- product specifications

shopping:
- add product to cart
- remove product from cart
- update cart quantity
- view cart
- checkout
- purchase-related shopping actions

order:
- view existing orders
- order status
- shipment tracking
- delivery status
- cancellation
- return
- refund
- problems with an existing order

support:
- FAQs
- company policies
- complaints
- troubleshooting
- general customer support

unknown:
- requests that do not fit any category above

IMPORTANT:
Return ONLY ONE WORD from this list:

product
shopping
order
support
unknown

Do not explain your answer.
Do not use markdown.
Do not return JSON.
Do not return YAML.

User request:
{message}
"""

    response = llm.invoke(prompt)

    raw = response.content.strip().lower()

    print("ROUTER RAW RESPONSE:", repr(raw))

    # -----------------------------------------
    # Normalize common model responses
    # -----------------------------------------

    if "product" in raw:
        intent = Intent.PRODUCT

    elif "shopping" in raw:
        intent = Intent.SHOPPING

    elif "order" in raw:
        intent = Intent.ORDER

    elif "support" in raw:
        intent = Intent.SUPPORT

    elif "unknown" in raw:
        intent = Intent.UNKNOWN

    else:
        intent = Intent.UNKNOWN

    return IntentClassification(
        intent=intent
    )