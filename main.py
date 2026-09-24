"""
API Backend (box 2): FastAPI. Also serves the web UI from static/.

Run:   uvicorn main:app --reload
UI:    http://127.0.0.1:8000          (DataMind web app)
Docs:  http://127.0.0.1:8000/docs     (Swagger UI - test the raw API)
"""
import json
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from data_hub import SUPPORTED, get_hub
from graph import run, stream

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app):
    get_hub()   # load data/ into DuckDB once at startup
    yield


app = FastAPI(title="DataMind API", version="0.2.0", lifespan=lifespan,
              description="Multi-agent RAG for data analytics: Supervisor, Data, SQL, RAG agents")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str
    debug: bool = False


def build_response(question: str, s: dict, debug: bool, seconds: float | None = None) -> dict:
    resp = {
        "question": question,
        "answer": s.get("final_answer"),
        "plan": s.get("plan"),
        "sql": s.get("sql_query"),
        "sql_error": s.get("sql_error"),
        "result": s.get("sql_result"),
        "documents": {"summary": s.get("rag_summary"), "citations": s.get("rag_citations")},
        "trace": s.get("trace"),
        "seconds": round(seconds, 2) if seconds is not None else None,
    }
    if debug:
        resp.update(selected_tables=s.get("selected_tables"), sql_attempts=s.get("sql_attempts"),
                    rag_chunks=s.get("rag_chunks"))
    return resp


# ------------------------------------------------------------------- UI
@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(STATIC_DIR / "index.html")


# --------------------------------------------------------------- status
@app.get("/health")
def health():
    try:
        from rag.store import source_counts
        n_docs = len(source_counts())
    except Exception:  # noqa: BLE001
        n_docs = 0
    return {"status": "ok", "provider": config.LLM_PROVIDER, "model": config.LLM_MODEL,
            "tables": get_hub().list_tables(), "documents": n_docs}


# ------------------------------------------------------------------ ask
@app.post("/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(400, "question is empty")
    t0 = time.perf_counter()
    s = run(req.question)
    return build_response(req.question, s, req.debug, time.perf_counter() - t0)


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Server-Sent Events: one 'step' event per agent, then 'done' with the full response."""
    if not req.question.strip():
        raise HTTPException(400, "question is empty")

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    def events():
        t0 = time.perf_counter()
        state = {}
        try:
            for node, update, state in stream(req.question):
                yield sse("step", {"node": node, "trace": update.get("trace", []),
                                   "plan": update.get("plan"),
                                   "elapsed": round(time.perf_counter() - t0, 2)})
            yield sse("done", build_response(req.question, state, req.debug,
                                             time.perf_counter() - t0))
        except Exception as e:  # noqa: BLE001
            yield sse("error", {"detail": str(e)})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------- tables
@app.get("/tables")
def tables():
    return get_hub().catalog()


@app.get("/tables/{name}/preview")
def table_preview(name: str, limit: int = Query(50, ge=1, le=500)):
    try:
        return get_hub().preview(name, limit)
    except KeyError:
        raise HTTPException(404, f"Table '{name}' not found")


@app.delete("/tables/{name}")
def delete_table(name: str):
    try:
        get_hub().drop_table(name)
    except KeyError:
        raise HTTPException(404, f"Table '{name}' not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"deleted": name}


@app.post("/upload/dataset")
def upload_dataset(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, f"Unsupported type {ext}. Use one of {sorted(SUPPORTED)}")
    dest = config.UPLOAD_DIR / Path(file.filename).name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        created = get_hub().load_file(dest)
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not read {dest.name}: {e}")
    return {"file": dest.name, "tables_created": created}


# ------------------------------------------------------------ documents
@app.get("/documents")
def documents():
    try:
        from rag.store import source_counts
        counts = source_counts()
        return {"documents": [{"name": n, "chunks": c} for n, c in counts.items()]}
    except Exception as e:  # noqa: BLE001 - e.g. embedding model not downloaded yet
        return {"documents": [], "error": str(e)}


@app.get("/documents/search")
def documents_search(q: str = Query(..., min_length=2), k: int = Query(5, ge=1, le=20)):
    from rag.store import search
    return {"query": q, "results": search(q, k=k)}


@app.post("/upload/document")
def upload_document(file: UploadFile = File(...)):
    from rag.ingest import SUPPORTED_DOCS, ingest_file
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_DOCS:
        raise HTTPException(400, f"Unsupported type {ext}. Use one of {sorted(SUPPORTED_DOCS)}")
    dest = config.DOCS_DIR / Path(file.filename).name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"file": dest.name, "chunks_indexed": ingest_file(dest)}


@app.delete("/documents/{name}")
def delete_document(name: str):
    from rag.store import delete_source, source_counts
    if name not in source_counts():
        raise HTTPException(404, f"Document '{name}' not indexed")
    delete_source(name)
    path = (config.DOCS_DIR / name).resolve()
    if config.DOCS_DIR.resolve() in path.parents and path.exists():
        path.unlink()
    return {"deleted": name}
