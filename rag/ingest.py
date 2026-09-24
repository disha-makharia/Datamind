"""
RAG pipeline, ingestion half (bottom row of the architecture slide):
Company Documents -> Python Doc Processing -> Chunking -> Local Embeddings -> ChromaDB

Run once (and again whenever docs change):
    python -m rag.ingest
"""
import hashlib
import re
import sys
from pathlib import Path

from pypdf import PdfReader

import config
from rag.store import get_collection

SUPPORTED_DOCS = {".pdf", ".txt", ".md"}


def load_document(path: Path) -> list[dict]:
    """Returns one entry per page (PDF) or one for the whole file (txt/md)."""
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return [{"text": page.extract_text() or "", "page": i + 1}
                for i, page in enumerate(reader.pages)]
    return [{"text": path.read_text(encoding="utf-8", errors="ignore"), "page": 1}]


def clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = config.CHUNK_SIZE,
               overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Paragraph/sentence-aware chunking with overlap.
    Packs sentences into chunks up to `size` chars; the tail of each chunk
    (about `overlap` chars) is repeated at the start of the next so a fact
    split across a boundary is still retrievable."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    chunks, current = [], ""
    for s in (s.strip() for s in sentences):
        if not s:
            continue
        if len(current) + len(s) + 1 <= size:
            current = f"{current} {s}".strip()
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap:]
            current = f"{tail[tail.find(' ') + 1:]} {s}".strip() if overlap else s
        else:  # single very long sentence
            chunks.append(s[:size])
            current = s[size - overlap:]
    if current:
        chunks.append(current)
    return chunks


def ingest_file(path: Path) -> int:
    collection = get_collection()
    ids, docs, metas = [], [], []
    for page in load_document(path):
        for i, chunk in enumerate(chunk_text(clean(page["text"]))):
            ids.append(hashlib.md5(f"{path.name}|{page['page']}|{i}".encode()).hexdigest())
            docs.append(chunk)
            metas.append({"source": path.name, "page": page["page"], "chunk": i})
    # remove old chunks of this file so re-ingesting an edited doc is clean
    collection.delete(where={"source": path.name})
    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def ingest_directory(directory: Path = config.DOCS_DIR) -> dict[str, int]:
    result = {}
    for f in sorted(Path(directory).iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_DOCS:
            result[f.name] = ingest_file(f)
            print(f"  {f.name}: {result[f.name]} chunks")
    return result


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else config.DOCS_DIR
    print(f"Ingesting documents from {target} ...")
    counts = ingest_directory(target)
    print(f"Done. {sum(counts.values())} chunks from {len(counts)} documents "
          f"stored in {config.CHROMA_DIR}")
