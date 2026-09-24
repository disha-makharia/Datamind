"""
Agent 2 - Data Agent
  * Finds the relevant dataset(s)/tables
  * Identifies the columns and schema needed
  * Hands a focused schema (+ join hints) to the SQL Agent

Why a separate agent? Real warehouses have hundreds of tables. Sending every
schema to the SQL prompt wastes tokens and confuses the model (the "schema
linking" problem from DIN-SQL / MAC-SQL in your literature review).
"""
import re

import llm
from data_hub import get_hub
from state import AgentState

SYSTEM = """ROLE: DATA
You are the Data Agent of DataMind. Given a data task and a database catalog,
select the tables and columns needed to answer it, and explain how to join them.

Rules:
- Only use table and column names that appear in the catalog, spelled exactly.
- Include key columns needed for joins (e.g. product_id, customer_id, order_id).
- Prefer the fewest tables that fully answer the task.
- If a value filter is needed (region, category...), note the exact value from the catalog.
- VALUE MATCHES (if given) are facts found by searching the actual data: a specific value
  from the question exists in that table/column. Always use those tables for such lookups.
- Tables marked "uploaded by the user" are the user's own data. When the question could be
  answered from either an uploaded table or a demo table, prefer the uploaded one.

Return ONLY a JSON object:
{
  "tables": [{"table": "name", "columns": ["col", ...], "reason": "why needed"}],
  "join_hints": ["sales.product_id = products.product_id", ...],
  "filter_hints": ["products.category = 'Electronics'", ...],
  "notes": "anything the SQL agent should know (e.g. revenue = total_amount)"
}"""


STOP = {"what", "which", "show", "give", "list", "total", "how", "many", "much", "the", "and",
        "for", "top", "why", "did", "does", "compare", "average", "count", "tell", "find"}


def candidate_values(question: str) -> list[str]:
    """Literal values worth looking up in the data: quoted text, ID-like tokens that
    contain digits (53-7769693, ORD000123, P010) and capitalised words (Mumbai, Electronics)."""
    out = [a or b for a, b in re.findall(r"'([^']{2,60})'|\"([^\"]{2,60})\"", question)]
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9_./-]*[A-Za-z0-9]", question):
        if re.fullmatch(r"(19|20)\d\d|\d{1,3}|q[1-4]", tok, re.I):
            continue                                   # years, small numbers, quarters
        if any(ch.isdigit() for ch in tok) and len(tok) >= 4:
            out.append(tok)
        elif tok[0].isupper() and len(tok) >= 3 and tok.lower() not in STOP:
            out.append(tok)
    return list(dict.fromkeys(out))[:8]


def data_agent_node(state: AgentState) -> dict:
    hub = get_hub()
    task = state.get("plan", {}).get("data_task") or state["question"]
    catalog = {t["table"]: {c["name"] for c in t["columns"]} for t in hub.catalog()}

    # value linking: search the real data for literal values from the question
    matches = hub.find_values(candidate_values(state["question"]))
    match_text = "\n".join(f"- '{m['value']}' found in {m['table']}.{m['column']} ({m['rows']} rows)"
                            for m in matches) or "- none"

    try:
        result = llm.chat_json(SYSTEM, f"CATALOG:\n{hub.describe_tables()}\n\n"
                                       f"VALUE MATCHES:\n{match_text}\n\n"
                                       f"USER QUESTION: {state['question']}\nDATA TASK: {task}")
    except Exception as e:  # noqa: BLE001
        result = {"tables": [], "notes": f"LLM error: {e}"}

    # --- validate against the real catalog (drop hallucinated names) -----
    selected, dropped = [], []
    for t in result.get("tables", []):
        name = t.get("table")
        if name not in catalog:
            dropped.append(name)
            continue
        cols = [c for c in t.get("columns", []) if c in catalog[name]]
        selected.append({"table": name, "columns": cols, "reason": t.get("reason", "")})

    if not selected:  # small DBs: safest fallback is "give the SQL agent everything"
        selected = [{"table": n, "columns": sorted(c), "reason": "fallback: all tables"}
                    for n, c in catalog.items()]

    # an ID-like value (contains a digit) pins the table: make sure it's included
    for m in matches:
        if any(ch.isdigit() for ch in m["value"]) and m["table"] not in [t["table"] for t in selected]:
            selected.insert(0, {"table": m["table"], "columns": sorted(catalog[m["table"]]),
                                "reason": f"contains the value '{m['value']}' in column {m['column']}"})

    names = [t["table"] for t in selected]
    schema_context = hub.describe_tables(names)
    hints = [f"The value '{m['value']}' exists in {m['table']}.{m['column']} "
             f"(filter with {m['table']}.{m['column']} = '{m['value']}')" for m in matches]
    hints += result.get("join_hints", []) + result.get("filter_hints", [])
    if result.get("notes"):
        hints.append(f"NOTE: {result['notes']}")

    msg = f"Data Agent: selected {names}"
    if matches:
        msg += f" (matched values {sorted({m['value'] for m in matches})})"
    if dropped:
        msg += f" (ignored unknown tables {dropped})"
    return {"selected_tables": selected, "schema_context": schema_context,
            "join_hints": hints, "trace": [msg]}
