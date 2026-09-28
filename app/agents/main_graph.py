from app.agents.orchestrator import build_main_graph
from app.db.database import SessionLocal

# LangGraph Studio supplies its own checkpointer. Compile the graph once to
# avoid constructing a second set of agents and tools over the same DB session.
_db = SessionLocal()
graph = build_main_graph(_db, with_checkpointer=False)

__all__ = ["build_main_graph", "graph"]
