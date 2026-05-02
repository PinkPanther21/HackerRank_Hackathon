"""
retriever.py
============
Loads all markdown docs from the data/ directory, chunks them,
builds embeddings, and provides semantic retrieval.
Includes caching for faster subsequent runs.
"""

import os
import re
import json
import numpy as np
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
# LAZY MODEL LOAD
# ─────────────────────────────────────────────
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("  Loading sentence-transformer model...", flush=True)
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ─────────────────────────────────────────────
# CHUNKING
# ─────────────────────────────────────────────
CHUNK_SIZE    = 400   # characters
CHUNK_OVERLAP = 80    # characters


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks at sentence/paragraph boundaries."""
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Split on double newlines first (paragraphs)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # If single paragraph is too large, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) + 1 <= chunk_size:
                        buf = (buf + " " + s).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = s
                if buf:
                    chunks.append(buf)
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c) > 40]


# ─────────────────────────────────────────────
# RETRIEVER CLASS
# ─────────────────────────────────────────────
class Retriever:
    """
    Loads all .md files from data/<company>/ directories,
    chunks them, and enables cosine-similarity retrieval.
    Uses caching for faster subsequent runs.
    """

    SUPPORTED_COMPANIES = {"hackerrank", "claude", "visa"}
    CACHE_FILE = Path(__file__).parent / "index_cache.json"

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        # company → list of (chunk_text, source_file)
        self._chunks:     dict[str, list[str]]       = {}
        # company → np.ndarray of shape (N, D)
        self._embeddings: dict[str, np.ndarray]      = {}

        self._load_all()
        self._embed_all()

    # ── Loading ──────────────────────────────────────────────────────────────

    def _load_all(self):
        for company in self.SUPPORTED_COMPANIES:
            folder = self.data_dir / company
            if not folder.exists():
                print(f"  ⚠  No data folder for '{company}' at {folder}")
                self._chunks[company] = []
                continue

            docs = []
            for path in sorted(folder.rglob("*.md")):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore").strip()
                    if len(text) > 60:
                        docs.append(text)
                except Exception:
                    pass

            chunks = []
            for doc in docs:
                chunks.extend(chunk_text(doc))

            self._chunks[company] = chunks
            print(f"  ✔  {company:<12} — {len(docs):>3} files → {len(chunks):>4} chunks")

    def _embed_all(self):
        # Try to load from cache first
        cache_data = self._load_cache()
        
        mdl = get_model()
        for company, chunks in self._chunks.items():
            if not chunks:
                self._embeddings[company] = np.array([])
                continue
            
            # Use cache if available and valid
            if cache_data and company in cache_data:
                cached_chunks = cache_data[company].get("chunks", [])
                cached_embs = cache_data[company].get("embeddings", [])
                # Verify cache matches current chunks
                if cached_chunks == chunks and len(cached_embs) > 0:
                    print(f"  📦 Loading {company} embeddings from cache...")
                    self._embeddings[company] = np.array(cached_embs, dtype=np.float32)
                    continue
            
            # Encode if no cache
            print(f"  ⚙️  Encoding {len(chunks)} chunks for {company}...", flush=True)
            embs = mdl.encode(
                chunks,
                batch_size=64,  # Increased for faster encoding
                show_progress_bar=True,
                device="cpu",
                convert_to_numpy=True,
                normalize_embeddings=True,   # unit vectors → dot = cosine
            )
            self._embeddings[company] = embs

        # Save cache for future runs
        self._save_cache()

    def _load_cache(self) -> Optional[dict]:
        """Load cached embeddings if available."""
        if not self.CACHE_FILE.exists():
            return None
        try:
            with open(self.CACHE_FILE, "r") as f:
                data = json.load(f)
            return data
        except Exception:
            return None

    def _save_cache(self):
        """Save embeddings to cache for faster subsequent runs."""
        cache_data = {}
        for company, embeddings in self._embeddings.items():
            if len(embeddings) > 0:
                cache_data[company] = {
                    "chunks": self._chunks[company],
                    "embeddings": embeddings.tolist()
                }
        try:
            with open(self.CACHE_FILE, "w") as f:
                json.dump(cache_data, f)
            print(f"  💾 Cached embeddings to {self.CACHE_FILE}")
        except Exception as e:
            print(f"  ⚠️  Failed to save cache: {e}")

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        company: str,
        top_k: int = 4,
        threshold: float = 0.25,
    ) -> list[str]:
        """
        Return top-k most relevant chunks for query from company's corpus.
        Falls back to all-company search if company-specific corpus is empty.
        """
        company_key = company.lower() if company else ""

        results = self._retrieve_from(query, company_key, top_k, threshold)

        # Fallback: search all corpora if nothing found
        if not results:
            all_results = []
            for c in self.SUPPORTED_COMPANIES:
                all_results.extend(self._retrieve_from(query, c, top_k=2, threshold=threshold))
            # De-dup and take top_k
            seen = set()
            for r in all_results:
                if r not in seen:
                    seen.add(r)
                    results.append(r)
                if len(results) >= top_k:
                    break

        return results

    def _retrieve_from(
        self,
        query: str,
        company_key: str,
        top_k: int,
        threshold: float,
    ) -> list[str]:
        chunks = self._chunks.get(company_key, [])
        embs   = self._embeddings.get(company_key, np.array([]))

        if not chunks or embs.size == 0:
            return []

        mdl = get_model()
        q_emb = mdl.encode(
            query,
            show_progress_bar=False,
            device="cpu",
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        scores  = embs @ q_emb                    # cosine (since normalized)
        indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for i in indices:
            if scores[i] >= threshold:
                results.append(chunks[i])

        # Always return at least the best chunk even below threshold
        if not results and len(indices) > 0:
            results.append(chunks[indices[0]])

        return results

    def total_docs(self) -> int:
        return sum(len(v) for v in self._chunks.values())
