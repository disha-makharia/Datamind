"""
Orchestrator (box 3 in the architecture): LangGraph agent coordinator.

Routes (decided by the Supervisor's plan):
  data only   : supervisor -> data_agent -> sql_agent -> interim_response
  data + docs : supervisor -> data_agent -> sql_agent -> rag_agent -> interim_response
  docs only   : supervisor -> rag_agent -> interim_response
  neither     : supervisor -> interim_response

RAG runs AFTER SQL on purpose: the RAG agent can then use the SQL findings
(e.g. "West Electronics fell in Jul-Sep") to pick out the right explanation.

Later: replace interim_response with Analysis -> Visualization -> Response agents.
"""
from langgraph.graph import END, START, StateGraph

from agents.data_agent import data_agent_node
from agents.interim_response import interim_response_node
from agents.rag_agent import rag_agent_node
from agents.sql_agent import route_after_sql, sql_agent_node
from agents.supervisor import route_after_supervisor, supervisor_node
from state import AgentState


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("data_agent", data_agent_node)
    g.add_node("sql_agent", sql_agent_node)
    g.add_node("rag_agent", rag_agent_node)
    g.add_node("interim_response", interim_response_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_after_supervisor,
                            {"data_agent": "data_agent", "rag_agent": "rag_agent",
                             "interim_response": "interim_response"})
    g.add_edge("data_agent", "sql_agent")
    g.add_conditional_edges("sql_agent", route_after_sql,
                            {"rag_agent": "rag_agent", "interim_response": "interim_response"})
    g.add_edge("rag_agent", "interim_response")
    g.add_edge("interim_response", END)
    return g.compile()


_app = None


def _get_app():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run(question: str) -> dict:
    return _get_app().invoke({"question": question, "trace": []})


def stream(question: str):
    """Yields (node_name, update, state_so_far) after each agent finishes.
    Used by the UI to light up agents live as they complete."""
    state: dict = {"question": question, "trace": []}
    for chunk in _get_app().stream({"question": question, "trace": []}, stream_mode="updates"):
        for node, update in chunk.items():
            update = update or {}
            for key, value in update.items():
                if key == "trace":
                    state["trace"] = state.get("trace", []) + list(value)
                else:
                    state[key] = value
            yield node, update, state
