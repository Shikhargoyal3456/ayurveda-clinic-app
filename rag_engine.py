"""Compatibility shim for legacy imports.

The canonical RAG implementation lives in `app.rag_engine`.
Keep this file as a thin re-export so older imports do not break.
"""

from app.rag_engine import AyurvedaRAGEngine, RetrievalResult, get_rag_engine

__all__ = ["AyurvedaRAGEngine", "RetrievalResult", "get_rag_engine"]
