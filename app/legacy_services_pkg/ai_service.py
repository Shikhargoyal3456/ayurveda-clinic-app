from app.rag.rag_engine import generate_ai_response


def analyze_symptoms(symptoms: str) -> str:
    return generate_ai_response(symptoms)
