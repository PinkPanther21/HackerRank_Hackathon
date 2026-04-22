"""Entry point for the Python starter.

The evaluator imports ``solve_ticket`` from this module. Do not rename or
remove it. Contract: see AGENTS.md §6.4.
"""

from __future__ import annotations

from typing import TypedDict


class Ticket(TypedDict, total=False):
    id: str
    subject: str
    body: str
    metadata: dict


class Resolution(TypedDict):
    answer: str
    confidence: float
    citations: list[str]


def solve_ticket(ticket: Ticket) -> Resolution:
    return {
        "answer": "",
        "confidence": 0.0,
        "citations": [],
    }


if __name__ == "__main__":
    sample: Ticket = {
        "id": "sample-1",
        "subject": "Unable to run a test case",
        "body": "My submission keeps timing out on the second test case.",
    }
    import json
    print(json.dumps(solve_ticket(sample), indent=2))
