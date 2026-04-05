from __future__ import annotations

import argparse
import pickle
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import fitz
import numpy as np

from app.config import settings

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("faiss-cpu is required to build the vector store.") from exc


warnings.filterwarnings("ignore", message=".*position_ids.*UNEXPECTED.*")


@dataclass
class DocumentChunk:
    text: str
    source_file: str
    chunk_id: str
    word_count: int


def ensure_runtime_dirs() -> None:
    settings.samhita_pdfs_dir.mkdir(parents=True, exist_ok=True)
    settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    (settings.static_dir / "images").mkdir(parents=True, exist_ok=True)


def discover_pdf_files(pdf_dir: Path | None = None) -> list[Path]:
    base_dir = pdf_dir or settings.samhita_pdfs_dir
    if not base_dir.exists():
        return []
    return sorted(path for path in base_dir.rglob("*.pdf") if path.is_file())


def extract_text_from_pdf(pdf_path: Path) -> str:
    text_parts: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)
    raw_text = "\n".join(text_parts)
    return re.sub(r"\s+", " ", raw_text).strip()


def chunk_text(
    text: str,
    chunk_size_words: int | None = None,
    chunk_overlap_words: int | None = None,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    # Default chunk size stays in the 300-400 word range for fast retrieval.
    size = chunk_size_words or settings.chunk_size_words
    overlap = chunk_overlap_words or settings.chunk_overlap_words
    if size < 100:
        raise ValueError("chunk_size_words must be at least 100.")
    if overlap >= size:
        raise ValueError("chunk_overlap_words must be smaller than chunk_size_words.")

    chunks: list[str] = []
    step = size - overlap
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            continue
        chunk = " ".join(window).strip()
        if len(window) < 100 and chunks:
            chunks[-1] = f"{chunks[-1]} {chunk}".strip()
            break
        chunks.append(chunk)
        if start + size >= len(words):
            break
    return chunks


def load_source_chunks(pdf_dir: Path | None = None) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for pdf_path in discover_pdf_files(pdf_dir):
        text = extract_text_from_pdf(pdf_path)
        for index, chunk in enumerate(chunk_text(text), start=1):
            chunks.append(
                DocumentChunk(
                    text=chunk,
                    source_file=pdf_path.name,
                    chunk_id=f"{pdf_path.stem}-{index}",
                    word_count=len(chunk.split()),
                )
            )
    return chunks


def _embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model, local_files_only=True)


def build_vector_store(force: bool = False) -> dict[str, int | bool | list[str]]:
    ensure_runtime_dirs()
    index_path = settings.vector_store_dir / "index.faiss"
    docs_path = settings.vector_store_dir / "docs.pkl"

    if index_path.exists() and docs_path.exists() and not force:
        with docs_path.open("rb") as handle:
            docs = pickle.load(handle)
        return {
            "rebuilt": False,
            "chunks": len(docs),
            "sources": sorted({item["source_file"] for item in docs}),
        }

    documents = load_source_chunks()
    if not documents:
        raise FileNotFoundError(
            f"No PDF files were found in {settings.samhita_pdfs_dir}. "
            "Add Samhita PDFs and run the loader again."
        )

    texts = [item.text for item in documents]
    embeddings = _embedding_model().encode(
        texts,
        batch_size=16,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    matrix = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)

    docs_payload = [
        {
            "text": item.text,
            "source_file": item.source_file,
            "chunk_id": item.chunk_id,
            "word_count": item.word_count,
        }
        for item in documents
    ]

    faiss.write_index(index, str(index_path))
    with docs_path.open("wb") as handle:
        pickle.dump(docs_payload, handle)

    return {
        "rebuilt": True,
        "chunks": len(docs_payload),
        "sources": sorted({item["source_file"] for item in docs_payload}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Samhita PDF vector store.")
    parser.add_argument("--force", action="store_true", help="Force a full rebuild of the FAISS index.")
    args = parser.parse_args()
    report = build_vector_store(force=args.force)
    print(
        f"Vector store ready. Rebuilt: {report['rebuilt']}. "
        f"Chunks indexed: {report['chunks']}."
    )


if __name__ == "__main__":
    main()
