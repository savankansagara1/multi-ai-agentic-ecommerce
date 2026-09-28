# Multi-AI Agentic E-Commerce System

A FastAPI e-commerce application with LangGraph workflows for product discovery, shopping, order management, and customer support.

## Project layout

- `app/api/routes/` — HTTP endpoints.
- `app/agents/` — conversational agents, domain graphs, shared state, and `orchestrator.py` for top-level routing.
- `app/services/` — database-backed product, cart, order, and support operations.
- `app/tools/` — LangChain tools that expose service operations to agents.
- `app/db/` — database setup, models, and seed data.
- `app/schemas/` — request and response schemas.
- `app/static/` — web interface assets.
- `alembic/` — database migrations.
- `tests/` — automated shopping/order and support/API tests.
- `examples/` — manual graph, agent, tool, and diagnostics demos.

## Run locally

Configure `DATABASE_URL` and the model settings in `.env`, apply migrations with `alembic upgrade head`, then start the API with `uvicorn app.main:app --reload`. The LangGraph Studio entry point is `app/agents/main_graph.py:graph`, configured in `langgraph.json`.

Run the automated suite with `python -m unittest discover -s tests`. Integration tests use the database configured in `.env`; run them against a disposable development database because checkout and cart operations commit changes.
