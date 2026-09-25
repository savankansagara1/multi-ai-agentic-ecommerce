import re
import random
from typing import Any
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload

from app.db.models.support import ProductDocument, DocumentChunk, AuditLog


class SupportService:

    @staticmethod
    def search_knowledge_base(
        db: Session,
        query: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Search policy and product troubleshooting chunks grounded in the database."""
        query_clean = query.strip()
        if not query_clean:
            return []

        # Tokenize query to match against chunk content and metadata
        stop_words = {"the", "a", "an", "is", "are", "and", "or", "in", "on", "at", "for", "to", "with", "my", "i", "what", "how", "can"}
        raw_words = re.findall(r"\b[a-zA-Z0-9_-]+\b", query_clean.lower())
        search_terms = [w for w in raw_words if w not in stop_words and len(w) >= 3]

        if not search_terms:
            search_terms = [query_clean.lower()]

        # Query all active document chunks with their parent document
        stmt = (
            select(DocumentChunk)
            .join(ProductDocument)
            .options(joinedload(DocumentChunk.document))
        )
        chunks = db.scalars(stmt).all()

        scored_chunks = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            doc_name_lower = chunk.document.file_name.lower()
            doc_type_lower = chunk.document.document_type.lower()
            metadata_str = str(chunk.chunk_metadata or {}).lower()

            score = 0
            # Term frequency match
            for term in search_terms:
                if term in content_lower:
                    score += content_lower.count(term) * 3
                if term in doc_name_lower:
                    score += 5
                if term in metadata_str:
                    score += 4
                if term in doc_type_lower:
                    score += 2

            # Exact phrase bonus
            if query_clean.lower() in content_lower:
                score += 15

            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:limit]

        results = []
        for score, chunk in top_chunks:
            results.append({
                "chunk_id": chunk.id,
                "document_file": chunk.document.file_name,
                "document_type": chunk.document.document_type,
                "topic": (chunk.chunk_metadata or {}).get("topic", "general"),
                "content": chunk.content,
                "relevance_score": score,
            })

        # Fallback if no direct term match: return top policy chunks
        if not results and chunks:
            for chunk in chunks[:limit]:
                results.append({
                    "chunk_id": chunk.id,
                    "document_file": chunk.document.file_name,
                    "document_type": chunk.document.document_type,
                    "topic": (chunk.chunk_metadata or {}).get("topic", "general"),
                    "content": chunk.content,
                    "relevance_score": 1,
                })

        return results

    @staticmethod
    def escalate_to_human(
        db: Session,
        user_id: int,
        issue_description: str,
        reason: str = "Automated resolution unavailable or complex customer complaint",
    ) -> dict[str, Any]:
        """Escalate unresolved or sensitive customer issues to a human support agent."""
        ticket_id = f"TICKET-2026-{random.randint(1000, 9999)}"

        audit = AuditLog(
            user_id=user_id,
            action="ESCALATE_TO_HUMAN",
            entity_type="support_ticket",
            entity_id=None,
            old_value=None,
            new_value={
                "ticket_id": ticket_id,
                "issue_description": issue_description,
                "reason": reason,
            },
        )
        db.add(audit)
        db.commit()

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "status": "escalated",
            "issue_description": issue_description,
            "reason": reason,
            "contact_window": "Within 24 business hours",
            "message": (
                f"Your issue has been escalated to our Human Support Specialist Team under Reference ID: {ticket_id}. "
                f"A senior representative has been briefed on your issue ('{issue_description}') "
                f"and will reach out to you via your registered email within 24 business hours."
            ),
        }

    @staticmethod
    def get_faqs(db: Session) -> list[dict[str, Any]]:
        """Retrieve common knowledge base chunks formatted as FAQs for customer self-service."""
        stmt = (
            select(DocumentChunk)
            .join(ProductDocument)
            .options(joinedload(DocumentChunk.document))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        chunks = db.scalars(stmt).all()
        faqs = []
        for c in chunks:
            topic = (c.chunk_metadata or {}).get("topic", "General")
            title = topic.replace("_", " ").title()
            faqs.append({
                "id": c.id,
                "topic": topic,
                "title": title,
                "document": c.document.file_name,
                "content": c.content,
            })
        return faqs

