"""
TEMPORARY node so you can demo agents 1-4 end to end.
Replace it later with: Analysis Agent -> Visualization Agent -> Response Agent.
It simply turns the SQL result + RAG summary into a readable answer.
"""
import json

import llm
from state import AgentState

SYSTEM = """ROLE: RESPONSE
You write the final answer for a business user. Use ONLY the SQL result and document
findings given. State key numbers (INR, with thousands separators). If documents explain
the reason, include it with its citation. If data is missing or the query failed, say so
plainly. Keep it under 150 words. Plain text, no markdown tables."""


def interim_response_node(state: AgentState) -> dict:
    plan = state.get("plan", {})
    if plan.get("intent") == "out_of_scope":
        return {"final_answer": "That question is outside what DataMind can answer from the "
                                "uploaded data and company documents.",
                "trace": ["Response: out of scope"]}

    parts = [f"QUESTION: {state['question']}"]
    if plan.get("needs_data"):
        if state.get("sql_error"):
            parts.append(f"SQL FAILED: {state['sql_error']}")
        else:
            r = state.get("sql_result", {})
            parts.append(f"SQL: {state.get('sql_query')}\nRESULT: " +
                         json.dumps({"columns": r.get("columns"), "rows": r.get("rows", [])[:30],
                                     "truncated": r.get("truncated")}, default=str))
    if plan.get("needs_docs"):
        parts.append(f"DOCUMENT FINDINGS: {state.get('rag_summary', '')}")

    try:
        answer = llm.chat(SYSTEM, "\n\n".join(parts))
    except Exception as e:  # noqa: BLE001
        answer = f"(could not generate answer: {e})"
    return {"final_answer": answer, "trace": ["Response: interim answer generated"]}
