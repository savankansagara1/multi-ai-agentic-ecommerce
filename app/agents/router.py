import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

from app.schemas.agent import Intent, IntentClassification

load_dotenv()

llm = ChatOllama(
    model="gpt-oss:120b-cloud",
    temperature=0,
)


def _explicit_intents(message: str) -> list[str]:
    """Identify clear domain signals without asking the LLM to guess."""
    text = re.sub(r"\s+", " ", message.lower()).strip()
    intents: list[str] = []

    # General capability and internal-data questions belong to the safe second-level handler.
    if re.search(
        r"\b(database|db|raw records|all records|credentials?|passwords?|secrets?|api keys?|"
        r"connection strings?|environment variables?|system prompts?|internal prompts?|developer prompts?)\b",
        text,
    ) or re.search(r"\b(?:select|insert|update|delete)\b.+\b(?:from|into|table)\b", text):
        return [Intent.UNKNOWN.value]
    if re.search(
        r"\b(?:what can (?:you|this assistant) (?:help|do)|what can i ask|what do you do|"
        r"available (?:features|functions|capabilities)|how does (?:this )?(?:shopping )?assistant work|"
        r"how do i use (?:this )?(?:shopping )?assistant)\b",
        text,
    ):
        return [Intent.UNKNOWN.value]

    shopping_patterns = (
        r"\b(?:view|show|see|check|status|current|clear|empty)\b.{0,35}\bcart\b",
        r"\b(?:add|put|remove|delete|update|change)\b.{0,80}\bcart\b",
        r"\b(?:checkout|check out|place (?:an? )?order|complete (?:my )?purchase|buy now|pay now)\b",
    )
    if any(re.search(pattern, text) for pattern in shopping_patterns):
        intents.append(Intent.SHOPPING.value)

    support_patterns = (
        r"\b(?:return|refund|cancellation|shipping|delivery)\s+policy\b",
        r"\b(?:warranty|guarantee|troubleshoot(?:ing)?|faq|policy|policies)\b",
        r"\b(?:how much|how long|what is|what are|tell me).{0,40}\b(?:shipping|delivery)\b.{0,35}\b(?:cost|fee|price|take|long|time)\b",
        r"\b(?:shipping|delivery)\s+(?:cost|fee|price|time)\b",
        r"\b(?:payment methods?|ways to pay|how (?:do|can) i pay|payment policy)\b",
        r"\bhow (?:do i|can i|to) return\b|\breturn (?:a|the|this) (?:product|item)\b",
        r"\b(?:speak|talk|connect)\s+(?:to|with)\s+(?:a\s+)?(?:human|person|representative|agent)\b",
        r"\b(?:damaged|broken|defective|wrong item|missing item|complaint|dispute|unresolved)\b",
    )
    if any(re.search(pattern, text) for pattern in support_patterns):
        intents.append(Intent.SUPPORT.value)

    order_patterns = (
        r"\b(?:my|previous|past|recent)\s+orders?\b",
        r"\b(?:order\s+(?:status|history|details|number|#)|track\s+(?:my\s+)?(?:order|package|shipment)|where\s+is\s+my\s+(?:order|package)|when\s+will\s+my\s+(?:order|package))\b",
        r"\b(?:cancel|return|refund)\b.{0,60}\b(?:my\s+)?order\b",
        r"\b(?:refund|return|cancellation)\s+(?:status|progress|request)\b",
        r"\bORD-[0-9A-Za-z-]+\b",
    )
    if any(re.search(pattern, text) for pattern in order_patterns):
        intents.append(Intent.ORDER.value)

    product_nouns = r"\b(?:products?|items?|laptops?|notebooks?|computers?|pcs?|phones?|smartphones?|mobiles?|tablets?|cameras?|headphones?|earbuds?)\b"
    product_actions = r"\b(?:show|list|find|search|browse|recommend|suggest|compare|comare|buy|purchase|price|cost|features?|specs?|specifications?|options?|available|availability|stock|inventory|how\s+many|under|below|best|which|what|sell|have|offer|carry|helpful|useful|suitable|good\s+for|work\s+for|stud(?:y|ies|ying))\b"
    if (
        (re.search(product_nouns, text) and re.search(product_actions, text))
        or re.search(r"\b(?:product\s+list|list\s+of\s+products?|catalog)\b", text)
        or re.search(r"\bwhat\s+(?:can|could)\s+i\s+buy\b", text)
    ):
        intents.append(Intent.PRODUCT.value)


    return list(dict.fromkeys(intents))


def detect_intents(message: str) -> list[str]:
    """Route clear requests directly; use the classifier only when rules are unsure."""
    explicit = _explicit_intents(message)
    if explicit:
        return explicit
    return [classify_intent(message).intent.value]


def classify_intent(message: str) -> IntentClassification:
    """Classify one request and default safely to unknown if uncertain or unavailable."""
    explicit = _explicit_intents(message)
    if len(explicit) == 1:
        return IntentClassification(intent=Intent(explicit[0]))
    if len(explicit) > 1:
        # This schema represents one intent; the graph's detect_intents handles compounds.
        return IntentClassification(intent=Intent.UNKNOWN)

    prompt = f"""You are the intent classifier for an e-commerce shopping assistant.
Choose exactly one label: product, shopping, order, support, unknown.

product: The user wants to discover, compare, or ask factual questions about products in the store.
shopping: The user wants to view or change a cart, check out, or make a purchase.
order: The user asks about their existing order, shipment, cancellation, return, or refund status.
support: The user asks about company policies, warranty, troubleshooting, a complaint, or human assistance.
unknown: The request is unrelated to this store, is only small talk, or does not clearly fit one of the four categories.

Do not guess a store-related intent just because the user asks a question. If the request is ambiguous or unrelated, answer unknown.
Return only the single lowercase label, with no explanation.

User request: {message}
"""
    try:
        response = llm.invoke(prompt)
        raw = str(response.content).strip().lower().strip("`\"' .\n")
        if raw in {intent.value for intent in Intent}:
            return IntentClassification(intent=Intent(raw))
    except Exception:
        # A routing failure should result in a clarification prompt, not a forced agent/tool.
        pass

    return IntentClassification(intent=Intent.UNKNOWN)
