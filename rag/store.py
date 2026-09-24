"""
ChromaDB vector store with local sentence-transformer embeddings (free, offline
after the first model download). Grok/Groq are only used for generation.
"""
import chromadb
from chromadb.utils import embedding_functions

import config

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=config.EMBED_MODEL)
        _collection = client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def search(query: str, k: int = config.RAG_TOP_K) -> list[dict]:
    """Semantic search. score = cosine similarity (1 = identical)."""
    col = get_collection()
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(k, col.count()))
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"text": text, "source": meta["source"], "page": meta["page"],
                     "score": round(1 - dist, 3)})
    return hits


def list_sources() -> list[str]:
    col = get_collection()
    if col.count() == 0:
        return []
    metas = col.get(include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in metas})


def source_counts() -> dict[str, int]:
    """{document name: number of chunks}"""
    col = get_collection()
    if col.count() == 0:
        return {}
    counts: dict[str, int] = {}
    for m in col.get(include=["metadatas"])["metadatas"]:
        counts[m["source"]] = counts.get(m["source"], 0) + 1
    return dict(sorted(counts.items()))


def delete_source(name: str) -> None:
    get_collection().delete(where={"source": name})
