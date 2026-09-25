import os
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.routes.products import router as products_router
from app.api.routes.cart import router as cart_router
from app.api.routes.orders import router as orders_router
from app.api.routes.support import router as support_router
from app.api.routes.chat import router as chat_router

app = FastAPI(
    title="Multi-AI Agentic E-Commerce System",
    description="Autonomous Multi-AI Agent E-Commerce platform using LangGraph, local Ollama LLMs, FastAPI, and PostgreSQL.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount API Routers under /api
app.include_router(chat_router, prefix="/api")
app.include_router(cart_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(support_router, prefix="/api")
app.include_router(products_router, prefix="/api")

# Backward compatibility routes
app.include_router(products_router)


@app.get("/", response_class=HTMLResponse)
def serve_home():
    """Serve the interactive Single Page Web Application UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Multi-AI Agentic E-Commerce System</h1><p>Visit <a href='/docs'>/docs</a> for API.</p>")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "multi-ai-ecommerce",
        "version": "1.0.0",
        "agents": ["product", "shopping", "order", "support", "router", "multi_intent"],
    }


@app.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))
    value = result.scalar_one()

    return {
        "database": "ok",
        "result": value,
    }