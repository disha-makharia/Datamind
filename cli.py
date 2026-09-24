"""
Quick terminal client - the fastest way to watch the agents work.

    python cli.py                                   # interactive
    python cli.py "Which product had the highest sales in 2025?"
"""
import sys

from graph import run


def show(state: dict) -> None:
    print("\n--- agent trace ---")
    for step in state.get("trace", []):
        print("  >", step)

    if state.get("sql_query"):
        print("\n--- SQL ---")
        print(state["sql_query"])
        for a in state.get("sql_attempts", []):
            if not a.get("ok"):
                print(f"  (attempt {a['attempt']} failed: {a.get('error', '')[:150]})")

    r = state.get("sql_result") or {}
    if r.get("columns"):
        print(f"\n--- result ({r['row_count']} rows{', truncated' if r.get('truncated') else ''}) ---")
        widths = [max(len(str(c)), *(len(str(row[i])) for row in r["rows"][:15])) if r["rows"]
                  else len(str(c)) for i, c in enumerate(r["columns"])]
        print(" | ".join(str(c).ljust(w) for c, w in zip(r["columns"], widths)))
        print("-+-".join("-" * w for w in widths))
        for row in r["rows"][:15]:
            print(" | ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        if r["row_count"] > 15:
            print(f"... {r['row_count'] - 15} more rows")

    if state.get("rag_summary"):
        print("\n--- from company documents ---")
        print(state["rag_summary"])

    print("\n=== ANSWER ===")
    print(state.get("final_answer", ""))
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show(run(" ".join(sys.argv[1:])))
    else:
        print("DataMind CLI - type a question (or 'exit')")
        while True:
            q = input("\n? ").strip()
            if q.lower() in ("exit", "quit", ""):
                break
            show(run(q))
