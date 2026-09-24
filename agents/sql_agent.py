"""
Agent 3 - SQL Agent
  * Creates a SQL query for DuckDB from the focused schema
  * Validates it (read-only, known tables) and runs it
  * Self-corrects: on an error (or an empty result) the error is fed back to
    the LLM and it rewrites the query, up to SQL_MAX_RETRIES times
    (the "refiner" idea from MAC-SQL / "self-correction" from DIN-SQL)
"""
import config
import llm
from data_hub import get_hub
from state import AgentState

SYSTEM = """ROLE: SQL
You are the SQL Agent of DataMind. Write ONE DuckDB SQL SELECT query that answers the task.

DuckDB rules:
- Only use tables/columns from the SCHEMA. Quote identifiers with double quotes only if needed.
- String literals use single quotes and must match the catalog values exactly (case-sensitive).
- Dates: order_date is a DATE. Use year(col), month(col), date_trunc('month', col),
  strftime(col, '%Y-%m'), or col BETWEEN DATE '2025-07-01' AND DATE '2025-09-30'.
- Quarters: quarter(col). Use round(x, 2) for money. Revenue = SUM(total_amount) unless told otherwise.
- Always give aggregated columns readable aliases (total_revenue, order_count, ...).
- For "top/highest/most" questions use ORDER BY ... DESC LIMIT n.
- For trends over time, GROUP BY the time bucket and ORDER BY it.
- Never modify data. No INSERT/UPDATE/DELETE/CREATE/COPY. No read_csv or file paths.

Return ONLY a JSON object: {"sql": "...", "explanation": "one sentence"}"""


def _prompt(state: AgentState, feedback: str = "") -> str:
    hints = "\n".join(f"- {h}" for h in state.get("join_hints", [])) or "- none"
    task = state.get("plan", {}).get("data_task") or state["question"]
    p = (f"SCHEMA:\n{state.get('schema_context', '')}\n"
         f"HINTS FROM DATA AGENT:\n{hints}\n\n"
         f"USER QUESTION: {state['question']}\nTASK: {task}")
    if feedback:
        p += f"\n\nYOUR PREVIOUS ATTEMPT FAILED:\n{feedback}\nFix the query."
    return p


def sql_agent_node(state: AgentState) -> dict:
    hub = get_hub()
    attempts, feedback = [], ""
    result, error, sql = None, None, ""
    fallback = None            # a query that ran but returned 0 rows
    empty_retry_used = False

    for attempt in range(1, config.SQL_MAX_RETRIES + 1):
        sql = ""
        try:
            out = llm.chat_json(SYSTEM, _prompt(state, feedback))
            sql = (out.get("sql") or "").strip()
            if not sql:
                raise ValueError("LLM returned no SQL")
            result = hub.run_query(sql)
            error = None
        except Exception as e:  # noqa: BLE001 - parse, guard and DuckDB errors all retry
            error = str(e)
            attempts.append({"attempt": attempt, "sql": sql, "ok": False, "error": error})
            feedback = f"SQL:\n{sql}\nERROR:\n{error}"
            continue

        attempts.append({"attempt": attempt, "sql": sql, "ok": True, "rows": result["row_count"]})
        if (result["row_count"] == 0 and not empty_retry_used
                and attempt < config.SQL_MAX_RETRIES):
            # empty can be correct, but is usually a wrong filter value -> one more look
            empty_retry_used, fallback = True, (sql, result)
            feedback = (f"SQL:\n{sql}\nIt ran but returned 0 rows. Check filter values against "
                        f"the catalog (exact spelling/case) and the date ranges. If 0 rows is "
                        f"genuinely correct, return the same query.")
            continue
        break

    if error and fallback:            # later attempts failed; keep the valid empty result
        (sql, result), error = fallback, None

    if error:
        return {"sql_query": sql, "sql_attempts": attempts, "sql_result": {},
                "sql_error": error,
                "trace": [f"SQL Agent: failed after {len(attempts)} attempts - {error[:120]}"]}
    return {"sql_query": sql, "sql_attempts": attempts, "sql_result": result, "sql_error": None,
            "trace": [f"SQL Agent: {result['row_count']} rows in {len(attempts)} attempt(s)"]}


def route_after_sql(state: AgentState) -> str:
    return "rag_agent" if state.get("plan", {}).get("needs_docs") else "interim_response"
