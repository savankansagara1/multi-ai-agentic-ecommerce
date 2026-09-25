from app.agents.day2_conditional_graph import build_main_graph
from app.db.database import SessionLocal

_db = SessionLocal()
graph = build_main_graph(_db, with_checkpointer=False)

__all__ = ["build_main_graph", "graph"]
