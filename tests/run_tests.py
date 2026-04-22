"""Local evaluator for the Python starter.

Usage:
    python tests/run_tests.py --lang py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_agent(lang: str):
    if lang != "py":
        print(f"run_tests.py only supports --lang py (got {lang!r})", file=sys.stderr)
        sys.exit(2)
    agent_path = REPO_ROOT / "starter" / "py" / "agent.py"
    spec = importlib.util.spec_from_file_location("agent", agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {agent_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "solve_ticket"):
        raise RuntimeError(f"solve_ticket not defined in {agent_path}")
    return module.solve_ticket


def score_resolution(res: dict, ticket: dict) -> float:
    if not isinstance(res, dict):
        return 0.0
    answer = res.get("answer", "")
    if not isinstance(answer, str):
        return 0.0
    signals = ticket.get("expected_signals") or []
    if not signals:
        return 1.0 if answer else 0.0
    hay = answer.lower()
    hits = sum(1 for s in signals if s.lower() in hay)
    return hits / len(signals)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="py")
    args = parser.parse_args()

    solve = load_agent(args.lang)
    tickets = json.loads((REPO_ROOT / "tests" / "tickets.json").read_text("utf-8"))

    total = 0.0
    for t in tickets:
        started = time.time()
        try:
            res = solve(t)
        except Exception as exc:
            print(f"[{t['id']}] threw: {exc}", file=sys.stderr)
            continue
        elapsed_ms = int((time.time() - started) * 1000)
        score = score_resolution(res, t)
        total += score
        conf = res.get("confidence") if isinstance(res, dict) else "?"
        print(f"[{t['id']}] score={score:.2f} time={elapsed_ms}ms conf={conf}")

    n = len(tickets)
    pct = (total / n) * 100 if n else 0
    print(f"\nTotal: {total:.2f} / {n} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
