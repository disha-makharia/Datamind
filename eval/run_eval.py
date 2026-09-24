"""
Evaluation for the "Research Parameters" slide:
  - SQL correctness  -> execution accuracy (does the agent's result match the gold query's result?)
  - Response time    -> seconds per question
  - Self-correction  -> how many SQL attempts were needed

Matching is lenient on purpose: column names/order and extra columns don't matter,
numbers are compared after rounding, row order is ignored.

    python eval/run_eval.py
Writes eval/results.csv for your report.
"""
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_hub import get_hub  # noqa: E402
from graph import run  # noqa: E402

HERE = Path(__file__).parent


def norm(v):
    if isinstance(v, float):
        return round(v, 1)
    if isinstance(v, int):
        return round(float(v), 1)
    return str(v).strip().lower()


def rows_match(gold: list, pred: list) -> bool:
    if len(gold) != len(pred):
        return False
    pred_rows = [Counter(norm(v) for v in r) for r in pred]
    for g in gold:
        g_counter = Counter(norm(v) for v in g)
        match = next((i for i, p in enumerate(pred_rows) if not (g_counter - p)), None)
        if match is None:
            return False
        pred_rows.pop(match)
    return True


def main():
    hub = get_hub()
    questions = json.loads((HERE / "questions.json").read_text())
    results = []
    for q in questions:
        gold = hub.run_query(q["gold_sql"])["rows"]
        t0 = time.perf_counter()
        s = run(q["question"])
        secs = time.perf_counter() - t0
        pred = (s.get("sql_result") or {}).get("rows", [])
        ok = rows_match(gold, pred)
        results.append({"id": q["id"], "question": q["question"], "correct": ok,
                        "sql_attempts": len(s.get("sql_attempts", [])), "seconds": round(secs, 2),
                        "agent_sql": s.get("sql_query", ""), "error": s.get("sql_error") or ""})
        print(f"[{'PASS' if ok else 'FAIL'}] {q['id']:>2} {secs:5.1f}s  {q['question']}")
        if not ok:
            print(f"        gold: {gold[:3]}\n        pred: {pred[:3]}")

    n = len(results)
    acc = sum(r["correct"] for r in results) / n
    print(f"\nExecution accuracy: {acc:.1%} ({sum(r['correct'] for r in results)}/{n})")
    print(f"Avg response time : {sum(r['seconds'] for r in results) / n:.1f}s")
    print(f"Avg SQL attempts  : {sum(r['sql_attempts'] for r in results) / n:.2f}")
    with open(HERE / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print(f"Saved {HERE / 'results.csv'}")


if __name__ == "__main__":
    main()
