"""
Agent 1 - Supervisor Agent
  * Understands the user question
  * Breaks it into tasks
  * Assigns tasks to other agents (decides the route through the graph)
"""
import json

import llm
from data_hub import get_hub
from state import AgentState

SYSTEM = """ROLE: SUPERVISOR
You are the Supervisor Agent of DataMind, a multi-agent data analytics system.
You do NOT answer the question. You plan which specialist agents must work on it.

Specialists:
- Data + SQL agents: answer questions from the structured TABLES below (counts, totals,
  top-N, trends over time, comparisons, filters). Use for anything numeric or "what/which/how many".
- RAG agent: searches company DOCUMENTS (reports, memos, policies) for reasons, context,
  policies, explanations. Use for "why", "what caused", "what is our policy", "what happened".
- Many business questions need BOTH: e.g. "Why did West sales drop in Q3 2025?" needs SQL to
  confirm/measure the drop and RAG to find the cause.

Return ONLY a JSON object with these keys:
{
  "intent": "data_only" | "docs_only" | "data_and_docs" | "out_of_scope",
  "needs_data": true/false,
  "needs_docs": true/false,
  "data_task": "precise instruction for the data/SQL agents, or empty string",
  "doc_query": "a short search query for the document store, or empty string",
  "needs_chart": true/false,
  "subtasks": ["ordered list of short steps"],
  "reasoning": "one sentence explaining the plan"
}
Use "out_of_scope" only for questions unrelated to the company's data or documents."""


def _fallback_plan(question: str) -> dict:
    """Keyword heuristic used only if the LLM call fails."""
    q = question.lower()
    why = any(w in q for w in ("why", "reason", "cause", "policy", "explain", "happened"))
    return {"intent": "data_and_docs" if why else "data_only", "needs_data": True,
            "needs_docs": why, "data_task": question, "doc_query": question if why else "",
            "needs_chart": any(w in q for w in ("trend", "chart", "plot", "over time", "monthly")),
            "subtasks": [], "reasoning": "fallback heuristic (LLM planning failed)"}


def supervisor_node(state: AgentState) -> dict:
    question = state["question"]
    hub = get_hub()
    tables = [f'{t["table"]}({", ".join(c["name"] for c in t["columns"])})'
              for t in hub.catalog()]
    try:
        from rag.store import list_sources
        docs = list_sources()
    except Exception:  # noqa: BLE001 - RAG optional at planning time
        docs = []

    user = (f"TABLES:\n" + "\n".join(tables) +
            f"\n\nDOCUMENTS: {json.dumps(docs) if docs else 'none indexed'}"
            f"\n\nQUESTION: {question}")
    try:
        plan = llm.chat_json(SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        plan = _fallback_plan(question)
        plan["error"] = str(e)

    # normalise / sanity-check the plan
    plan.setdefault("needs_data", plan.get("intent") in ("data_only", "data_and_docs"))
    plan.setdefault("needs_docs", plan.get("intent") in ("docs_only", "data_and_docs"))
    plan["needs_data"], plan["needs_docs"] = bool(plan["needs_data"]), bool(plan["needs_docs"])
    if plan["needs_docs"] and not docs:
        plan["needs_docs"] = False
        plan["note"] = "No documents indexed; skipping RAG. Run: python -m rag.ingest"
    if plan["needs_data"] and not plan.get("data_task"):
        plan["data_task"] = question
    if plan["needs_docs"] and not plan.get("doc_query"):
        plan["doc_query"] = question

    route = [n for n, on in (("data", plan["needs_data"]), ("rag", plan["needs_docs"])) if on]
    return {"plan": plan,
            "trace": [f"Supervisor: intent={plan.get('intent')} route={route or ['none']} "
                      f"- {plan.get('reasoning', '')}"]}


def route_after_supervisor(state: AgentState) -> str:
    plan = state.get("plan", {})
    if plan.get("needs_data"):
        return "data_agent"
    if plan.get("needs_docs"):
        return "rag_agent"
    return "interim_response"
