from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AyurTermCategory, AyurvedicTerm


router = APIRouter(prefix="/api/ayurveda", tags=["ayurveda-terms"])


def _term_summary(term: AyurvedicTerm) -> dict[str, Any]:
    return {
        "id": term.id,
        "term": term.term,
        "sanskrit_term": term.sanskrit_term,
        "meaning": term.meaning,
        "category": term.category,
        "samhita": term.samhita,
        "pronunciation_guide": term.pronunciation_guide,
    }


def _term_detail(term: AyurvedicTerm) -> dict[str, Any]:
    return {
        **_term_summary(term),
        "ipa_pronunciation": term.ipa_pronunciation,
        "clinical_significance": term.clinical_significance,
        "chapter": term.chapter,
        "verse_number": term.verse_number,
        "verse_sanskrit": term.verse_sanskrit,
        "verse_translation": term.verse_translation,
        "commentary_name": term.commentary_name,
        "commentary_text": term.commentary_text,
        "commentary_translation": term.commentary_translation,
        "audio_url": term.audio_url,
    }


@router.get("/terms/search")
async def search_terms(
    query: str = Query(default=""),
    category: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    search = db.query(AyurvedicTerm)
    clean_query = query.strip()
    clean_category = category.strip()

    if clean_query:
        like_query = f"%{clean_query}%"
        search = search.filter(
            or_(
                AyurvedicTerm.term.ilike(like_query),
                AyurvedicTerm.sanskrit_term.ilike(like_query),
                AyurvedicTerm.meaning.ilike(like_query),
            )
        )

    if clean_category:
        search = search.filter(AyurvedicTerm.category == clean_category)

    results = search.order_by(AyurvedicTerm.term.asc()).limit(50).all()
    return {"success": True, "count": len(results), "results": [_term_summary(term) for term in results]}


@router.get("/terms/{term_id}")
async def get_term_detail(term_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    term = db.query(AyurvedicTerm).filter(AyurvedicTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"success": True, "term": _term_detail(term)}


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)) -> dict[str, Any]:
    categories = db.query(AyurTermCategory).order_by(AyurTermCategory.name.asc()).all()
    return {
        "success": True,
        "categories": [
            {"name": category.name, "icon": category.icon, "description": category.description}
            for category in categories
        ],
    }


@router.post("/terms/pronounce")
async def generate_pronunciation(
    data: dict[str, str] = Body(default={}),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    term_name = (data.get("term") or "").strip()
    if not term_name:
        raise HTTPException(status_code=400, detail="Term is required")

    term = db.query(AyurvedicTerm).filter(AyurvedicTerm.term.ilike(term_name)).first()
    guide = term.pronunciation_guide if term else ""
    ipa = term.ipa_pronunciation if term else ""
    pronunciation = "\n".join(
        line
        for line in [
            f"IPA: {ipa}" if ipa else "",
            f"Simplified: {guide}" if guide else f"Say {term_name} slowly, separating each syllable clearly.",
            "Audio tips: Keep the vowels open and unhurried; Sanskrit consonants should be crisp.",
        ]
        if line
    )
    return {"success": True, "term": term_name, "pronunciation": pronunciation}


@router.get("/by-samhita/{samhita_name}")
async def get_terms_by_samhita(samhita_name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    terms = (
        db.query(AyurvedicTerm)
        .filter(AyurvedicTerm.samhita.ilike(f"%{samhita_name}%"))
        .order_by(AyurvedicTerm.term.asc())
        .all()
    )
    return {
        "success": True,
        "samhita": samhita_name,
        "count": len(terms),
        "terms": [
            {"id": term.id, "term": term.term, "verse_number": term.verse_number, "meaning": term.meaning}
            for term in terms
        ],
    }
