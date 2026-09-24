"""
The shared state that flows through the LangGraph. Each agent reads what it
needs and returns ONLY the keys it changes; LangGraph merges them.
`trace` uses operator.add, so every agent appends to it instead of overwriting.
"""
import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    # input
    question: str

    # 1. Supervisor Agent
    plan: dict[str, Any]          # intent, needs_data, needs_docs, data_task, doc_query, ...

    # 2. Data Agent
    selected_tables: list[dict]   # [{table, columns, reason}]
    schema_context: str           # schema text handed to the SQL agent
    join_hints: list[str]

    # 3. SQL Agent
    sql_query: str
    sql_attempts: list[dict]      # every attempt with its error, for debugging/eval
    sql_result: dict              # {columns, rows, row_count, truncated}
    sql_error: str | None

    # 4. RAG Agent
    rag_chunks: list[dict]        # raw retrieved chunks with source + page
    rag_summary: str              # what the documents say that is relevant
    rag_citations: list[str]

    # temporary until Analysis / Visualization / Response agents exist
    final_answer: str

    trace: Annotated[list[str], operator.add]
