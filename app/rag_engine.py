from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ai_fallback import fallback_handler
from app.config import settings
from app.pdf_loader import build_vector_store, ensure_runtime_dirs
from services.ai_provider import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL, chat_with_gemini, chat_with_groq

try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"builtin type (SwigPyPacked|SwigPyObject|swigvarlink) has no __module__ attribute",
            category=DeprecationWarning,
        )
        import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("faiss-cpu is required for retrieval.") from exc


logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    source_file: str
    text: str
    score: float
    chunk_id: str


def extract_relevant_chunks(
    query: str,
    samhita_texts: list[str],
    top_k: int = 5,
    min_relevance: float = 0.08,
) -> list[dict[str, Any]]:
    """
    Extract the most relevant Samhita text chunks for a given query.
    Uses TF-IDF cosine similarity locally as a fallback helper.
    """
    if not samhita_texts:
        return []

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True,
        )
        all_texts = [query] + samhita_texts
        vectors = vectorizer.fit_transform(all_texts)
        query_vector = vectors[0:1]
        doc_vectors = vectors[1:]
        similarities = cosine_similarity(query_vector, doc_vectors)[0]
        top_indices = similarities.argsort()[-top_k:][::-1]

        relevant: list[dict[str, Any]] = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_relevance:
                relevant.append(
                    {
                        "text": samhita_texts[idx],
                        "relevance_score": round(score, 4),
                    }
                )
        return relevant
    except Exception as exc:
        logger.warning("RAG retrieval error, using unranked fallback: %s", exc)
        return [{"text": text, "relevance_score": 0.0} for text in samhita_texts[:top_k]]


class AyurvedaRAGEngine:
    def __init__(self) -> None:
        self._model = None
        self._docs: list[dict[str, Any]] | None = None
        self._faiss_index = None
        self._resource_lock = Lock()
        self._ollama_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ollama-call")
        self._memory_cache: dict[str, dict[str, Any]] = {}
        self._redis_warning_logged = False

    def _record_ai_failure(self, stage: str, error: str, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp": int(time.time()),
            "stage": stage,
            "error": error,
            "provider": "ollama",
            "model": self._ollama_model(),
            "url": self._ollama_url(),
        }
        if extra:
            payload.update(extra)

        try:
            log_path = Path(self._settings_value("ai_failure_log_path", settings.base_dir / "logs" / "ai_failures.jsonl"))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except OSError as exc:
            logger.warning("Unable to write AI failure log: %s", exc)

    def _settings_value(self, attr_name: str, fallback: Any) -> Any:
        return getattr(settings, attr_name, fallback)

    def _ollama_url(self) -> str:
        return self._settings_value("ollama_api_url", getattr(settings, "OLLAMA_URL", "http://localhost:11434"))

    def _ollama_model(self) -> str:
        return self._settings_value("ollama_model", getattr(settings, "OLLAMA_MODEL", "llama2"))

    def _top_k(self) -> int:
        return int(self._settings_value("faiss_top_k", 3))

    def _timeout(self) -> int:
        return int(self._settings_value("ollama_timeout_seconds", 30))

    def _soft_timeout(self) -> int:
        configured = int(self._settings_value("ollama_soft_timeout_seconds", 18))
        return max(3, min(configured, self._timeout(), 10))

    def _model_instance(self):
        if self._model is None:
            with self._resource_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    model_name = self._settings_value("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
                    self._model = SentenceTransformer(model_name, local_files_only=True)
        return self._model

    def _docs_path(self) -> Path:
        return Path(self._settings_value("vector_store_dir", settings.base_dir / "vector_store")) / "docs.pkl"

    def _faiss_path(self) -> Path:
        return Path(self._settings_value("vector_store_dir", settings.base_dir / "vector_store")) / "index.faiss"

    def _faiss_rebuild_lock_path(self) -> Path:
        return Path(self._settings_value("vector_store_dir", settings.base_dir / "vector_store")) / ".faiss_rebuild.lock"

    def _generate_endpoint(self) -> str:
        return f"{self._ollama_url().rstrip('/')}/api/generate"

    def _cache_key(self, symptoms: str, patient_context: str) -> str:
        payload = json.dumps({"symptoms": symptoms, "patient_context": patient_context}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_client(self):
        redis_url = getattr(settings, "redis_url", "")
        cache_enabled = getattr(settings, "ai_cache_enabled", False)
        if not cache_enabled or not redis_url:
            return None
        try:
            import redis  # type: ignore

            return redis.from_url(redis_url, decode_responses=True)
        except Exception as exc:  # pragma: no cover
            if not self._redis_warning_logged:
                logger.warning("Redis cache unavailable: %s", exc)
                self._redis_warning_logged = True
            return None

    def _cleanup_stale_rebuild_lock(self, lock_path: Path) -> None:
        if not lock_path.exists():
            return
        try:
            if time.time() - lock_path.stat().st_mtime > 600:
                lock_path.unlink()
                logger.warning("Removed stale FAISS rebuild lock at %s", lock_path)
        except OSError as exc:
            logger.warning("Failed to evaluate rebuild lock %s: %s", lock_path, exc)

    def prepare(self, force_rebuild: bool = False) -> dict[str, Any]:
        ensure_runtime_dirs()
        lock_path = self._faiss_rebuild_lock_path()
        self._cleanup_stale_rebuild_lock(lock_path)
        if lock_path.exists():
            return {"rebuilt": False, "chunks": 0, "sources": [], "message": "Rebuild already in progress."}

        lock_path.write_text(str(time.time()), encoding="utf-8")
        try:
            report = build_vector_store(force=force_rebuild)
            self._docs = None
            self._faiss_index = None
            return report
        finally:
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except OSError:
                logger.warning("Failed to remove FAISS rebuild lock at %s", lock_path)

    def _load_store(self) -> None:
        if self._docs is not None and self._faiss_index is not None:
            return

        with self._resource_lock:
            if self._docs is not None and self._faiss_index is not None:
                return
            if not self._docs_path().exists() or not self._faiss_path().exists():
                self.prepare(force_rebuild=False)

            with self._docs_path().open("rb") as handle:
                self._docs = pickle.load(handle)
            self._faiss_index = faiss.read_index(str(self._faiss_path()))

    def warm_up(self) -> dict[str, Any]:
        ensure_runtime_dirs()
        report = {"embedding_model_loaded": False, "vector_store_loaded": False, "indexed_chunks": 0}
        try:
            self._model_instance()
            report["embedding_model_loaded"] = True
        except Exception as exc:  # pragma: no cover
            logger.exception("Embedding model warmup failed: %s", exc)
        try:
            if self._docs_path().exists() and self._faiss_path().exists():
                self._load_store()
                report["vector_store_loaded"] = True
                report["indexed_chunks"] = len(self._docs or [])
        except Exception as exc:  # pragma: no cover
            logger.exception("Vector store warmup failed: %s", exc)
        return report

    def warm_up_llm(self) -> dict[str, Any]:
        if GEMINI_API_KEY:
            return {"llm_warmed": True, "message": "Vertex AI Gemini is configured.", "provider": "gemini"}
        if GROQ_API_KEY:
            return {"llm_warmed": True, "message": "Groq API key is configured.", "provider": "groq"}
        return {"llm_warmed": False, "message": "No remote AI provider is configured.", "provider": "fallback"}

    def ensure_ollama_available(self, timeout_seconds: int = 3, allow_retries: bool = True) -> tuple[bool, str | None]:
        probe_url = f"{self._ollama_url().rstrip('/')}/api/tags"
        attempts = 2 if allow_retries else 1
        for attempt in range(attempts):
            started_at = time.perf_counter()
            try:
                response = requests.get(probe_url, timeout=timeout_seconds)
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError:
                        return False, "Ollama health probe returned invalid JSON."
                    if isinstance(payload, dict) and "models" in payload:
                        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                        logger.info("Ollama health probe succeeded in %sms", duration_ms)
                        return True, None
                    return False, "Ollama health probe returned an unexpected payload."
                if response.status_code < 500:
                    message = f"Ollama health probe returned HTTP {response.status_code}."
                    self._record_ai_failure("availability_probe", message, {"status_code": response.status_code})
                    return False, message
            except requests.Timeout as exc:
                if attempt == attempts - 1:
                    message = f"Ollama server timed out at {self._ollama_url()}. {exc}"
                    self._record_ai_failure("availability_probe", message)
                    return False, message
            except requests.RequestException as exc:
                if attempt == attempts - 1:
                    message = f"Ollama server is not reachable at {self._ollama_url()}. {exc}"
                    self._record_ai_failure("availability_probe", message)
                    return False, message
            time.sleep(0.5 * (2**attempt))
        return False, f"Ollama server is not reachable at {self._ollama_url()}."

    def ollama_status(self, timeout_seconds: int = 2, allow_retries: bool = False) -> dict[str, Any]:
        if getattr(settings, "ai_enabled", True) is False:
            return {
                "status": "degraded",
                "available": False,
                "mode": "fallback",
                "warning": "AI is disabled by configuration.",
                "model": self._ollama_model(),
                "provider": "ollama",
                "url": self._ollama_url(),
            }

        available, message = self.ensure_ollama_available(timeout_seconds=timeout_seconds, allow_retries=allow_retries)
        return {
            "status": "ready" if available else "degraded",
            "available": available,
            "mode": "ollama" if available else "fallback",
            "warning": message if not available else None,
            "model": self._ollama_model(),
            "provider": "ollama",
            "url": self._ollama_url(),
        }

    def gemini_status(self) -> dict[str, Any]:
        return {
            "configured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL,
        }

    def groq_status(self) -> dict[str, Any]:
        return {
            "configured": bool(GROQ_API_KEY),
            "model": GROQ_MODEL,
        }

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        try:
            self._load_store()
            docs = self._docs or []
            if not docs:
                return []
            limited_top_k = min(top_k or self._top_k(), len(docs))
            query_vector = self._model_instance().encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            scores, indices = self._faiss_index.search(np.asarray(query_vector, dtype="float32"), limited_top_k)
            results: list[RetrievalResult] = []
            for score, index in zip(scores[0], indices[0], strict=False):
                if index < 0 or index >= len(docs):
                    continue
                item = docs[int(index)]
                results.append(
                    RetrievalResult(
                        source_file=str(item["source_file"]),
                        text=str(item["text"]),
                        score=float(score),
                        chunk_id=str(item.get("chunk_id", index)),
                    )
                )
            return results
        except Exception as exc:
            logger.exception("FAISS retrieval failed: %s", exc)
            return []

    def _build_prompt(
        self,
        symptoms: str,
        patient_context: str,
        passages: list[RetrievalResult],
        specialty: str = "ayurveda",
    ) -> str:
        def _compact_text(value: str, limit: int) -> str:
            compact = " ".join(value.split())
            if len(compact) <= limit:
                return compact
            return compact[: max(0, limit - 3)].rstrip() + "..."

        selected_passages = passages[:2]
        context_block = "\n".join(
            f"- {Path(item.source_file).name} [{item.chunk_id}]: {_compact_text(item.text, 220)}"
            for item in selected_passages
        )
        SPECIALTY_PROMPTS = {
            "ayurveda": (
                "You are a senior Ayurvedic physician (Vaidya) with 20 years "
                "of clinical experience in classical Samhita-based practice. "
                "You reason from the retrieved Charaka Samhita, Sushruta "
                "Samhita, and Ashtanga Hridayam passages provided. "
                "Always ground your response in classical Ayurvedic theory. "
                "Structure your response as: "
                "1. Nidana (probable cause and dosha vitiation) "
                "2. Samprapti (pathogenesis in Ayurvedic terms) "
                "3. Chikitsa (treatment: shodhana or shamana approach, "
                "   key herbs, formulations) "
                "4. Pathya-Apathya (dietary and lifestyle advice). "
                "Be concise — under 200 words. "
                "Do not recommend anything outside classical Ayurvedic scope. "
                "Use the patient's symptoms, diagnosis, and notes actively even when retrieval is partial. "
                "Give a best-effort Samhita-aligned draft instead of refusing when case details are available. "
                "If limitations remain, mention them briefly after the draft rather than replacing the whole answer with a refusal."
            ),
            "modern_medicine": (
                "You are a senior clinician (MD, Internal Medicine) with "
                "evidence-based practice in a busy Indian hospital. "
                "You follow current clinical guidelines (WHO, ICMR, API). "
                "Structure your response as: "
                "1. Differential Diagnosis (top 3, most likely first, "
                "   with brief reasoning) "
                "2. Red Flag Symptoms (list any that require urgent referral) "
                "3. Investigations Suggested (CBC, LFT, imaging etc. — "
                "   only what is clinically justified) "
                "4. First-line Treatment (drug class, generic name, "
                "   standard Indian dosing) "
                "5. Patient Counselling (1-2 key points). "
                "Be concise — under 220 words. "
                "Always mention drug allergies and contraindication check. "
                "Do not prescribe specific brands. Use generic drug names only."
            ),
            "homeopathy": (
                "You are a senior homeopathic physician (BHMS/MD Homeopathy) "
                "with deep knowledge of classical homeopathy, materia medica, "
                "and Kent's repertory. "
                "You follow the totality of symptoms approach. "
                "Structure your response as: "
                "1. Constitutional Analysis (miasm, temperament, thermal state) "
                "2. Rubric Selection (3-5 key rubrics from the case) "
                "3. Remedy Indicated (top 2 remedies with justification, "
                "   potency, and repetition schedule) "
                "4. Auxiliary Measures (diet, lifestyle, avoid suppressants). "
                "Be concise — under 200 words. "
                "Always consider the totality — do not prescribe on "
                "pathological diagnosis alone. "
                "Note if the case needs a nosode or intercurrent remedy."
            ),
            "dental": (
                "You are a senior dental surgeon (BDS/MDS) practicing in "
                "India with expertise in restorative, endodontic, and "
                "periodontal treatment. "
                "Structure your response as: "
                "1. Clinical Assessment (probable diagnosis based on "
                "   symptoms and tooth number provided) "
                "2. Radiographic Recommendation (what X-ray view is needed "
                "   and what to look for) "
                "3. Treatment Plan (step-by-step: immediate symptom support, "
                "   definitive treatment, restoration plan) "
                "4. Patient Instructions (post-treatment care, warning signs, "
                "   follow-up timeline). "
                "Be concise — under 200 words. "
                "Always mention infection control and antibiotic stewardship. "
                "Suggest referral to specialist if case complexity warrants it."
            ),
            "physiotherapy": (
                "You are a senior physiotherapist (BPT/MPT) with expertise "
                "in musculoskeletal, neurological, and sports rehabilitation "
                "in an Indian clinical setting. "
                "Structure your response as: "
                "1. Clinical Reasoning (likely diagnosis, tissue involved, "
                "   stage: acute/subacute/chronic) "
                "2. Assessment Findings to Confirm (special tests, ROM "
                "   measurement, postural analysis) "
                "3. Treatment Protocol (manual therapy techniques, "
                "   electrotherapy modalities if indicated, "
                "   therapeutic exercises — sets, reps, frequency) "
                "4. Home Exercise Program (2-3 safe exercises with "
                "   clear instructions) "
                "5. Goals and Prognosis (expected recovery timeline, "
                "   return to activity milestones). "
                "Be concise — under 220 words. "
                "Always consider red flags for non-mechanical causes. "
                "Note if imaging or specialist referral is needed."
            ),
        }
        system_instruction = SPECIALTY_PROMPTS.get(
            specialty, SPECIALTY_PROMPTS["ayurveda"]
        )
        prompt = (
            f"{system_instruction}\n\n"
            f"Retrieved Context:\n{context_block}\n\n"
            f"Patient Context:\n{_compact_text(patient_context or 'Not provided.', 180)}\n\n"
            f"Symptoms:\n{_compact_text(symptoms, 220)}\n\n"
        )
        return _compact_text(prompt, 1400)

    def _request_ollama(self, prompt: str) -> requests.Response:
        request_timeout = min(self._timeout(), self._soft_timeout())
        logger.info(
            "Ollama request started: model=%s timeout_seconds=%s prompt_chars=%s",
            self._ollama_model(),
            request_timeout,
            len(prompt),
        )
        return requests.post(
            self._generate_endpoint(),
            json={
                "model": self._ollama_model(),
                "prompt": prompt,
                "stream": False,
            },
            timeout=request_timeout,
        )

    def _request_gemini(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "You are an Ayurveda clinical assistant."},
            {"role": "user", "content": prompt},
        ]
        return chat_with_gemini(messages)

    def _request_groq(self, prompt: str) -> str:
        return chat_with_groq(
            "You are an Ayurveda clinical assistant.",
            prompt,
            temperature=0.3,
        )

    def _extract_ollama_error(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            body_text = response.text.strip()
            return body_text or f"Ollama returned HTTP {response.status_code}."

        if isinstance(payload, dict):
            error_message = str(payload.get("error", "")).strip()
            if error_message:
                return error_message
        return json.dumps(payload, ensure_ascii=True)

    def _context_passages(self, passages: list[RetrievalResult]) -> list[dict[str, Any]]:
        return [
            {"source_file": item.source_file, "chunk_id": item.chunk_id, "score": round(item.score, 4)}
            for item in passages
        ]

    def _fallback_payload(self, symptoms: str, patient_context: str, passages: list[RetrievalResult]) -> dict[str, Any]:
        fallback = fallback_handler.get_response(symptoms, patient_context)
        logger.warning("Using fallback AI response for symptoms length=%s", len(symptoms))
        return {
            "answer": fallback["response"],
            "sources": [item.source_file for item in passages] or ["fallback"],
            "context_passages": self._context_passages(passages),
            "source": "fallback",
            "mode": "fallback",
            "source_metadata": {"provider": "fallback", "topics": fallback.get("topics", [])},
            "warning": "Primary AI model unavailable. Using fallback knowledge base.",
        }

    def generate_clinical_response(
        self,
        symptoms: str,
        patient_context: str = "",
        specialty: str = "ayurveda",
    ) -> dict[str, Any]:
        normalized = symptoms.strip()
        if not normalized:
            return {"answer": "Symptoms are required before AI analysis can run.", "sources": [], "context_passages": [], "source": "validation", "mode": "validation"}

        cache_key = self._cache_key(normalized, patient_context)
        cache = self._cache_client()
        if cache is not None:
            try:
                cached_payload = cache.get(cache_key)
                if cached_payload:
                    return json.loads(cached_payload)
            except Exception:
                pass
        if cache_key in self._memory_cache:
            return dict(self._memory_cache[cache_key])

        passages = self.retrieve(normalized, top_k=self._top_k())
        # For non-Ayurveda specialties, skip RAG and go
        # directly to Gemini with symptom context only
        if specialty != "ayurveda":
            passages = []
        if specialty == "ayurveda" and not passages:
            payload = {
                "answer": "No Samhita knowledge is indexed yet. Add PDFs to `samhita_pdfs/` and rebuild the vector store.",
                "sources": [],
                "context_passages": [],
                "source": "fallback",
                "mode": "fallback",
            }
            self._memory_cache[cache_key] = payload
            return payload

        if getattr(settings, "ai_enabled", True) is False:
            payload = self._fallback_payload(normalized, patient_context, passages)
            self._memory_cache[cache_key] = payload
            return payload

        prompt = self._build_prompt(
            normalized, patient_context, passages, specialty
        )
        last_error: str | None = None
        if settings.is_testing:
            payload = self._fallback_payload(normalized, patient_context, passages)
            self._memory_cache[cache_key] = payload
            if cache is not None:
                try:
                    cache.setex(cache_key, 3600, json.dumps(payload))
                except Exception:
                    pass
            return payload
        if GEMINI_API_KEY:
            try:
                response = self._request_gemini(prompt)
                payload = {
                    "answer": response,
                    "sources": [item.source_file for item in passages],
                    "context_passages": self._context_passages(passages),
                    "source": "gemini",
                    "mode": "gemini",
                    "provider": "gemini",
                    "source_metadata": {"provider": "gemini", "model": GEMINI_MODEL},
                }
                self._memory_cache[cache_key] = payload
                if cache is not None:
                    try:
                        cache.setex(cache_key, 3600, json.dumps(payload))
                    except Exception:
                        pass
                return payload
            except Exception as e:
                last_error = str(e)
                logger.warning("Gemini failed, trying Groq fallback if configured: %s", e)

        if GROQ_API_KEY:
            try:
                response = self._request_groq(prompt)
                payload = {
                    "answer": response,
                    "sources": [item.source_file for item in passages],
                    "context_passages": self._context_passages(passages),
                    "source": "groq",
                    "mode": "groq",
                    "provider": "groq",
                    "source_metadata": {"provider": "groq", "model": GROQ_MODEL},
                }
                self._memory_cache[cache_key] = payload
                if cache is not None:
                    try:
                        cache.setex(cache_key, 3600, json.dumps(payload))
                    except Exception:
                        pass
                return payload
            except Exception as e:
                last_error = str(e)
                logger.warning("Groq failed, using fallback response: %s", e)

        payload = self._fallback_payload(normalized, patient_context, passages)
        payload["warning"] = last_error or payload["warning"]
        self._memory_cache[cache_key] = payload
        if cache is not None:
            try:
                cache.setex(cache_key, 3600, json.dumps(payload))
            except Exception:
                pass
        return payload


RAGEngine = AyurvedaRAGEngine
_engine: AyurvedaRAGEngine | None = None


def get_rag_engine() -> AyurvedaRAGEngine:
    global _engine
    if _engine is None:
        _engine = AyurvedaRAGEngine()
        try:
            _engine._model_instance()
        except Exception as exc:  # pragma: no cover
            logger.warning("Embedding model preload skipped: %s", exc)
    return _engine
