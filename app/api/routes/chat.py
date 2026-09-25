from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langgraph.checkpoint.memory import MemorySaver

from app.db.database import get_db
from app.agents.day2_conditional_graph import build_main_graph

router = APIRouter(
    prefix="/chat",
    tags=["Agent Chat"],
)

# Shared memory checkpointer so multi-turn conversations persist across API calls
_chat_checkpointer = MemorySaver()


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="User message or command")
    user_id: int = Field(default=1, description="User ID for scoping orders and cart")
    thread_id: str = Field(default="session_web_default", description="Unique conversation thread ID")


class ChatMessageResponse(BaseModel):
    response: str
    intent: str | None = None
    awaiting_confirmation: bool = False
    pending_action: dict[str, Any] | None = None
    thread_id: str


@router.post("/", response_model=ChatMessageResponse)
def chat_with_agent(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """Invoke the Multi-AI Agent system with session state and confirmation tracking."""
    try:
        graph = build_main_graph(db=db, checkpointer=_chat_checkpointer)
        config = {"configurable": {"thread_id": request.thread_id}}

        result = graph.invoke(
            {
                "user_id": request.user_id,
                "message": request.message,
            },
            config=config,
        )

        return ChatMessageResponse(
            response=str(result.get("response", "")),
            intent=result.get("intent"),
            awaiting_confirmation=bool(result.get("awaiting_confirmation", False)),
            pending_action=result.get("pending_action"),
            thread_id=request.thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

