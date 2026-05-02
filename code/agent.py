"""
Multi-Domain Support Triage Agent
==================================
Terminal-based agent that processes support tickets across HackerRank, Claude, and Visa.
Uses RAG + LLM reasoning via Gemini API for classification, routing, and response generation.
"""

import csv
import sys
import os
import json
import time
import argparse
from pathlib import Path

from retriever import Retriever
from classifier import classify_ticket, infer_company
from llm import call_llm
from safety import safety_check

# ─────────────────────────────────────────────
# PATHS  (resolve relative to this script)
# ─────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR    = SCRIPT_DIR.parent / "data"

# ─────────────────────────────────────────────
# ESCALATION TRIGGERS
# ─────────────────────────────────────────────
HARD_ESCALATE_KEYWORDS = [
    "fraud", "unauthorized transaction", "stolen card", "identity theft",
    "account hacked", "account compromised", "legal action", "lawsuit",
    "chargeback", "dispute transaction", "money missing", "money stolen",
    "phishing", "scam", "extortion", "blackmail",
]

SOFT_ESCALATE_KEYWORDS = [
    "refund", "billing error", "overcharged", "double charged",
    "cannot access account", "locked out", "forgot password",
    "account suspended", "account banned", "data breach",
    "sensitive data", "personal information exposed",
]


def should_escalate(issue_text: str, classification: dict) -> tuple[bool, str]:
    """Return (escalate: bool, reason: str)."""
    lower = issue_text.lower()

    for kw in HARD_ESCALATE_KEYWORDS:
        if kw in lower:
            return True, f"Hard escalation trigger: '{kw}'"

    # LLM-classified escalation
    if classification.get("escalate"):
        return True, classification.get("escalation_reason", "LLM flagged escalation")

    # Soft triggers → still escalate
    for kw in SOFT_ESCALATE_KEYWORDS:
        if kw in lower:
            return True, f"Sensitive topic: '{kw}'"

    return False, ""


# ─────────────────────────────────────────────
# CORE PROCESSING
# ─────────────────────────────────────────────
def process_ticket(row: dict, retriever: Retriever) -> dict:
    issue   = row.get("Issue", row.get("issue", "")).strip()
    subject = row.get("Subject", row.get("subject", "")).strip()
    company = row.get("Company", row.get("company", "")).strip()

    combined_text = f"{subject}\n{issue}".strip() if subject else issue

    # ── 1. Safety check (prompt injection / abuse) ──────────────────────────
    safety_result = safety_check(combined_text)
    if safety_result["flagged"]:
        return {
            "status":        "escalated",
            "product_area":  "security",
            "response":      "Your message could not be processed. It has been flagged for review.",
            "justification": f"Safety filter triggered: {safety_result['reason']}",
            "request_type":  "invalid",
        }

    # ── 2. Infer company if missing ─────────────────────────────────────────
    if not company or company.lower() in ("none", ""):
        company = infer_company(combined_text)

    # ── 3. Retrieve relevant docs ───────────────────────────────────────────
    docs = retriever.retrieve(combined_text, company, top_k=4)
    context = "\n\n---\n\n".join(docs) if docs else "No relevant documentation found."

    # ── 4. LLM-based classification + response generation ───────────────────
    classification = classify_ticket(combined_text, company, context)

    escalate, escalation_reason = should_escalate(combined_text, classification)

    product_area = classification.get("product_area", "general")
    request_type = classification.get("request_type", "product_issue")

    # ── 5. Generate response ─────────────────────────────────────────────────
    if escalate:
        response = (
            "Thank you for reaching out. This issue requires attention from our "
            "specialized support team and has been escalated. A representative will "
            "contact you shortly. Please do not share any sensitive information "
            "(passwords, card numbers) in follow-up messages."
        )
        justification = (
            f"Escalated due to: {escalation_reason}. "
            f"Product area: {product_area}. "
            f"Classification: {request_type}."
        )
        status = "escalated"
    else:
        response = generate_grounded_response(combined_text, company, context, classification)
        justification = (
            f"Replied based on corpus retrieval ({len(docs)} doc(s) retrieved). "
            f"Product area: {product_area}. Request type: {request_type}. "
            f"Company: {company}."
        )
        status = "replied"

    return {
        "status":        status,
        "product_area":  product_area,
        "response":      response,
        "justification": justification,
        "request_type":  request_type,
    }


def generate_grounded_response(
    issue: str, company: str, context: str, classification: dict
) -> str:
    """
    Ask the LLM to produce a grounded, user-facing response from the retrieved context.
    """
    prompt = f"""You are a support agent for {company}. Answer the user's issue using ONLY the provided documentation below.
Do NOT invent policies, features, or steps not mentioned in the documentation.
If the documentation does not cover the issue, say so politely and suggest contacting support.

--- DOCUMENTATION ---
{context}
--- END DOCUMENTATION ---

User's issue:
{issue}

Write a clear, concise, helpful support response (2–5 sentences). Do not repeat the user's question."""

    reply = call_llm(prompt, max_tokens=400)
    return reply.strip()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Multi-Domain Support Triage Agent")
    parser.add_argument("--input",  default=str(SCRIPT_DIR.parent / "support_tickets" / "support_tickets.csv"))
    parser.add_argument("--output", default=str(SCRIPT_DIR.parent / "support_tickets" / "output.csv"))
    parser.add_argument("--sample", action="store_true", help="Run on sample_support_tickets.csv instead")
    parser.add_argument("--limit",  type=int, default=0, help="Process only first N tickets (0 = all)")
    args = parser.parse_args()

    if args.sample:
        args.input  = str(SCRIPT_DIR.parent / "support_tickets" / "sample_support_tickets.csv")
        args.output = str(SCRIPT_DIR.parent / "support_tickets" / "sample_output.csv")

    print(f"\n{'='*60}")
    print("  Multi-Domain Support Triage Agent")
    print(f"{'='*60}")
    print(f"  Input:  {args.input}")
    print(f"  Output: {args.output}")
    print(f"{'='*60}\n")

    # Load retriever (builds index once)
    print("Loading document index...", flush=True)
    retriever = Retriever(DATA_DIR)
    print(f"Index ready. ({retriever.total_docs()} docs loaded)\n")

    # Read tickets
    rows = []
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if args.limit:
        rows = rows[: args.limit]

    total    = len(rows)
    results  = []
    errors   = 0

    print(f"Processing {total} ticket(s)...\n")

    for idx, row in enumerate(rows, 1):
        ticket_id = row.get("id", row.get("ID", idx))
        try:
            result = process_ticket(row, retriever)
            results.append(result)

            # Pretty terminal output
            status_icon = "✅" if result["status"] == "replied" else "🔴"
            print(
                f"[{idx:>4}/{total}] {status_icon}  "
                f"{result['status'].upper():<10}  "
                f"{result['product_area']:<22}  "
                f"{result['request_type']}"
            )

        except Exception as e:
            errors += 1
            results.append({
                "status":        "escalated",
                "product_area":  "unknown",
                "response":      "An internal error occurred. This ticket has been escalated.",
                "justification": f"Processing error: {str(e)}",
                "request_type":  "invalid",
            })
            print(f"[{idx:>4}/{total}] ⚠️   ERROR: {e}", file=sys.stderr)

        # Polite rate-limit buffer for LLM calls
        if idx < total:
            time.sleep(0.3)

    # Write output
    out_fields = ["status", "product_area", "response", "justification", "request_type"]
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # Summary
    replied   = sum(1 for r in results if r["status"] == "replied")
    escalated = sum(1 for r in results if r["status"] == "escalated")

    print(f"\n{'='*60}")
    print(f"  ✔  Done — {total} tickets processed")
    print(f"  ↳  Replied:   {replied}")
    print(f"  ↳  Escalated: {escalated}")
    if errors:
        print(f"  ⚠  Errors:    {errors}")
    print(f"  Output → {args.output}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
