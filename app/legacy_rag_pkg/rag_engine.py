import requests
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import EMBEDDING_MODEL, KNOWLEDGE_BASE_DIR, OLLAMA_MODEL, OLLAMA_URL


model: SentenceTransformer | None = None
documents: list[str] = []
doc_embeddings = None


def load_samhita_texts() -> list[str]:
    texts: list[str] = []

    for file_path in sorted(KNOWLEDGE_BASE_DIR.glob("*.txt")):
        texts.append(file_path.read_text(encoding="utf-8"))

    return texts


def _get_embedding_resources():
    global model, documents, doc_embeddings

    if model is None:
        model = SentenceTransformer(EMBEDDING_MODEL)

    if not documents:
        documents = load_samhita_texts()

    if doc_embeddings is None and documents:
        doc_embeddings = model.encode(documents)

    return model, documents, doc_embeddings


def retrieve_knowledge(query: str) -> str:
    model_instance, loaded_documents, loaded_embeddings = _get_embedding_resources()

    if not loaded_documents:
        return "No samhita knowledge files are available."

    query_embedding = model_instance.encode([query])
    similarities = cosine_similarity(query_embedding, loaded_embeddings)[0]
    best_index = similarities.argmax()
    return loaded_documents[best_index]


def generate_ai_response(symptoms: str) -> str:
    context = retrieve_knowledge(symptoms)
    prompt = f"""
You are an expert Ayurveda doctor.

Use the following Ayurvedic knowledge from Samhitas to answer.

Knowledge:
{context}

Patient symptoms:
{symptoms}

Give:
1. Possible dosha imbalance
2. Ayurvedic reasoning
3. Suggested herbs or lifestyle advice
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    return result["response"]
