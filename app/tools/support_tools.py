from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.services.support_service import SupportService


def create_support_tools(db: Session):

    @tool
    def search_knowledge_base(
        query: str,
        limit: int = 4,
    ):
        """Search policy documents, warranties, returns, refunds, shipping rules, and troubleshooting guides.

        Use this whenever the user asks questions regarding:
        - Return, replacement, and refund policies or timelines
        - Shipping costs, delivery schedules, and carrier tracking
        - Order cancellation rules
        - Product warranty coverage, repairs, and diagnostics
        - Troubleshooting steps for laptops and phones (battery, display, charging)
        """
        return SupportService.search_knowledge_base(
            db=db,
            query=query,
            limit=limit,
        )

    @tool
    def escalate_to_human(
        user_id: int,
        issue_description: str,
        reason: str = "Customer complaint requiring manual specialist intervention",
    ):
        """Escalate an unresolved, sensitive, or disputed issue to a human support agent.

        Use this when:
        - Automated solutions cannot resolve the customer's problem
        - The user received damaged or wrong items and requests human review
        - The user explicitly asks to speak to an agent or representative
        - Complex payment or refund disputes arise
        """
        return SupportService.escalate_to_human(
            db=db,
            user_id=user_id,
            issue_description=issue_description,
            reason=reason,
        )

    return {
        "search_knowledge_base": search_knowledge_base,
        "escalate_to_human": escalate_to_human,
    }

