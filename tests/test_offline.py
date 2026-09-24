"""
Offline test: runs the full LangGraph with a FAKE LLM and FAKE document search.
No API key, no internet, no credits. Proves the wiring, routing, SQL guard and
self-correction loop work before you plug in Grok.

    python -m pytest tests -q        (or)        python tests/test_offline.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm  # noqa: E402
from agents import rag_agent as rag_mod  # noqa: E402
from agents import supervisor as sup_mod  # noqa: E402
from graph import build_graph  # noqa: E402

WHY_Q = "Why did Electronics sales in the West region drop in Q3 2025?"
GOOD_SQL = ("SELECT quarter(s.order_date) AS qtr, round(sum(s.total_amount), 2) AS revenue "
            "FROM sales s JOIN products p ON s.product_id = p.product_id "
            "JOIN customers c ON s.customer_id = c.customer_id "
            "WHERE p.category = 'Electronics' AND c.region = 'West' AND year(s.order_date) = 2025 "
            "GROUP BY qtr ORDER BY qtr")
calls = {"sql": 0}


def fake_chat_json(system: str, user: str) -> dict:
    role = system.split("\n", 1)[0]
    if role == "ROLE: SUPERVISOR":
        return {"intent": "data_and_docs", "needs_data": True, "needs_docs": True,
                "data_task": "Quarterly 2025 Electronics revenue for West region customers",
                "doc_query": "West region electronics decline Q3 2025 cause",
                "needs_chart": True, "subtasks": [], "reasoning": "needs numbers and cause"}
    if role == "ROLE: DATA":
        return {"tables": [{"table": "sales", "columns": ["order_date", "total_amount", "product_id",
                                                          "customer_id"], "reason": "revenue"},
                           {"table": "products", "columns": ["product_id", "category"], "reason": "cat"},
                           {"table": "customers", "columns": ["customer_id", "region"], "reason": "reg"},
                           {"table": "made_up_table", "columns": ["x"], "reason": "hallucination"}],
                "join_hints": ["sales.product_id = products.product_id"], "notes": "revenue = total_amount"}
    if role == "ROLE: SQL":
        calls["sql"] += 1
        if calls["sql"] == 1:   # first attempt: broken column -> must self-correct
            return {"sql": "SELECT sum(amount) FROM sales", "explanation": "bad"}
        return {"sql": GOOD_SQL, "explanation": "quarterly revenue"}
    if role == "ROLE: RAG":
        return {"relevant": True, "summary": "Bhiwandi DC flooded on 7 July 2025 "
                "[NovaMart_Q3_2025_Business_Review.pdf, p.1]", "citations": ["Q3 review p.1"]}
    raise AssertionError(f"unexpected role {role}")


def fake_chat(system: str, user: str, **_) -> str:
    return "West Electronics revenue fell in Q3 2025 because the Bhiwandi warehouse flooded."


def fake_search(query, k=4):
    return [{"text": "On 7 July 2025, heavy monsoon rainfall flooded the Bhiwandi distribution "
                     "centre...", "source": "NovaMart_Q3_2025_Business_Review.pdf", "page": 1,
             "score": 0.71}]


def test_full_pipeline():
    llm.chat_json, llm.chat = fake_chat_json, fake_chat
    rag_mod.search = fake_search
    sup_mod.__dict__["list_sources"] = lambda: ["NovaMart_Q3_2025_Business_Review.pdf"]
    import rag.store
    rag.store.list_sources = lambda: ["NovaMart_Q3_2025_Business_Review.pdf"]

    s = build_graph().invoke({"question": WHY_Q, "trace": []})
    for line in s["trace"]:
        print(" >", line)
    print("SQL attempts:", [(a["attempt"], a["ok"]) for a in s["sql_attempts"]])
    print("Result:", s["sql_result"]["columns"], s["sql_result"]["rows"])

    assert [t["table"] for t in s["selected_tables"]] == ["sales", "products", "customers"]
    assert s["sql_attempts"][0]["ok"] is False and s["sql_attempts"][-1]["ok"] is True
    rows = dict(s["sql_result"]["rows"])
    assert rows[3] < rows[2] * 0.7, "Q3 West Electronics should be well below Q2"
    assert "Bhiwandi" in s["rag_summary"]
    assert s["final_answer"]


if __name__ == "__main__":
    test_full_pipeline()
    print("\nOK - graph wiring, routing, schema validation and SQL self-correction work.")
