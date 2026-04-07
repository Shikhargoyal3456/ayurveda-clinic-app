from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import requests

from app.ai_fallback import fallback_handler
from app.config import settings
from app.pdf_loader import build_vector_store, ensure_runtime_dirs
from services.ai_provider import GEMINI_API_KEY, GEMINI_MODEL, chat_with_gemini

try:
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
        available, message = self.ensure_ollama_available()
        return {"llm_warmed": available, "message": message}

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
        specialty_prompts = {
            "ayurveda": (
                "You are an experienced Ayurvedic physician. "
                "Use the retrieved Samhita context below. "
                "Return: 1. Possible Ayurvedic diagnosis "
                "2. Dosha imbalance 3. Suggested approach. "
                "Keep under 180 words."
            ),
            "modern_medicine": (
                "You are an experienced MBBS/MD physician. "
                "Provide evidence-based clinical guidance. "
                "Return: 1. Likely diagnosis 2. Differential diagnoses "
                "3. Suggested investigations 4. Treatment approach. "
                "Keep under 180 words."
            ),
            "homeopathy": (
                "You are an experienced homeopathic physician. "
                "Return: 1. Constitutional analysis "
                "2. Suggested remedies with potency "
                "3. Lifestyle advice. Keep under 180 words."
            ),
            "dental": (
                "You are an experienced dental surgeon. "
                "Return: 1. Likely dental diagnosis "
                "2. Recommended procedure 3. Patient instructions. "
                "Keep under 180 words."
            ),
            "physiotherapy": (
                "You are an experienced physiotherapist. "
                "Return: 1. Assessment findings "
                "2. Rehabilitation protocol "
                "3. Home exercise plan. Keep under 180 words."
            ),
        }
        system_instruction = specialty_prompts.get(
            specialty, specialty_prompts["ayurveda"]
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
                logger.warning("Gemini failed, falling back: %s", e)

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
