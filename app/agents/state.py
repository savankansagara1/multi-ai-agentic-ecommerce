from typing import TypedDict, Any


class AgentState(TypedDict, total=False):
    user_id: int
    message: str
    intent: str
    intents: list[str] | None

    messages: list[Any]
    response: Any

    # Pending transactional action details awaiting user confirmation
    pending_action: dict[str, Any] | None
    awaiting_confirmation: bool

    # Which domain owns the pending confirmation ("shopping" or "order")
    pending_domain: str | None

    # Ambiguity options when multiple product variants match
    active_options: list[dict[str, Any]] | None
    pending_quantity: int | None

    # Immediate tool action to execute in tools node
    action_to_execute: dict[str, Any] | None