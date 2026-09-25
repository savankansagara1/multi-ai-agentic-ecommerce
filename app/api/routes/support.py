from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.support_service import SupportService

router = APIRouter(
    prefix="/support",
    tags=["Customer Support & Knowledge Base"],
)


class EscalateRequest(BaseModel):
    user_id: int = Field(default=1)
    issue_description: str
    reason: str = Field(default="Escalated via web assistant")


@router.get("/faqs")
def get_faqs(db: Session = Depends(get_db)):
    """Retrieve grounded knowledge base FAQs and policies."""
    return SupportService.get_faqs(db=db)


@router.get("/search")
def search_knowledge_base(
    q: str = Query(..., min_length=2),
    limit: int = Query(4, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Perform RAG search on knowledge base and policy chunks."""
    return SupportService.search_knowledge_base(db=db, query=q, limit=limit)


@router.post("/escalate")
def escalate_issue(
    request: EscalateRequest,
    db: Session = Depends(get_db),
):
    """Escalate a customer issue and create an official human support ticket."""
    return SupportService.escalate_to_human(
        db=db,
        user_id=request.user_id,
        issue_description=request.issue_description,
        reason=request.reason,
    )

