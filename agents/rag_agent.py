"""
Agent 4 - RAG Agent
  * Searches company documents (ChromaDB semantic search)
  * Finds reasons behind trends or changes
  * Returns relevant context WITH citations (source file + page)
"""
import json

import config
import llm
from rag.store import search
from state import AgentState

SYSTEM = """ROLE: RAG
You are the RAG Agent of DataMind. You receive a question, optional SQL findings, and
excerpts retrieved from company documents. Extract ONLY what the excerpts actually say that
helps answer the question (causes, context, dates, policies). Do not invent facts.
If the excerpts are not relevant, say so.

Return ONLY a JSON object:
{
  "relevant": true/false,
  "summary": "2-5 sentences of relevant findings, each followed by [source, p.N]",
  "citations": ["file.pdf p.N", ...]
}"""

MIN_SCORE = 0.15   # drop chunks that are clearly unrelated (cosine similarity)


def rag_agent_node(state: AgentState) -> dict:
    plan = state.get("plan", {})
    query = plan.get("doc_query") or state["question"]

    try:
        hits = [h for h in search(query, k=config.RAG_TOP_K) if h["score"] >= MIN_SCORE]
    except Exception as e:  # noqa: BLE001
        return {"rag_chunks": [], "rag_summary": "", "rag_citations": [],
                "trace": [f"RAG Agent: retrieval failed - {e}"]}

    if not hits:
        return {"rag_chunks": [], "rag_summary": "No relevant company documents found.",
                "rag_citations": [], "trace": [f"RAG Agent: 0 relevant chunks for '{query}'"]}

    excerpts = "\n\n".join(f"[{i}] ({h['source']}, p.{h['page']}, score={h['score']})\n{h['text']}"
                           for i, h in enumerate(hits, 1))
    sql_findings = ""
    if state.get("sql_result"):
        r = state["sql_result"]
        sql_findings = json.dumps({"columns": r["columns"], "rows": r["rows"][:20]}, default=str)

    try:
        out = llm.chat_json(SYSTEM, f"QUESTION: {state['question']}\n\n"
                                    f"SQL FINDINGS: {sql_findings or 'none'}\n\n"
                                    f"EXCERPTS:\n{excerpts}")
        summary = out.get("summary", "") if out.get("relevant", True) else \
            "Retrieved documents did not contain relevant information."
        citations = out.get("citations", [])
    except Exception as e:  # noqa: BLE001 - still return raw chunks
        summary, citations = f"(summary failed: {e})", []

    return {"rag_chunks": hits, "rag_summary": summary, "rag_citations": citations,
            "trace": [f"RAG Agent: {len(hits)} chunks from "
                      f"{sorted({h['source'] for h in hits})}"]}
