"""
classifier.py
=============
LLM-powered ticket classification.
Returns product_area, request_type, escalate flag, and escalation_reason.
"""

from llm import call_llm_json


# ─────────────────────────────────────────────
# PRODUCT AREA TAXONOMY  (per-company)
# ─────────────────────────────────────────────
PRODUCT_AREAS = {
    "hackerrank": [
        "assessments", "coding_challenges", "account_access", "billing",
        "candidate_experience", "integrations", "proctoring", "team_management",
        "results_reports", "api", "general",
    ],
    "claude": [
        "api_access", "billing", "claude_ai_app", "model_capabilities",
        "account_access", "data_privacy", "usage_limits", "claude_code",
        "enterprise", "safety_content", "general",
    ],
    "visa": [
        "card_activation", "fraud_dispute", "transaction_issue", "card_replacement",
        "account_access", "rewards", "merchant_issues", "international_use",
        "contactless_payments", "billing_statement", "general",
    ],
    "general": ["general"],
}

REQUEST_TYPES = ["product_issue", "feature_request", "bug", "invalid"]


def classify_ticket(issue: str, company: str, context: str) -> dict:
    """
    Use LLM to classify the ticket and decide escalation.
    Returns dict with: product_area, request_type, escalate, escalation_reason.
    """
    company_key  = company.lower() if company else "general"
    valid_areas  = PRODUCT_AREAS.get(company_key, PRODUCT_AREAS["general"])

    prompt = f"""You are a support triage classifier for {company}.

Given the following support ticket and relevant documentation, classify the ticket.

--- TICKET ---
{issue}

--- RELEVANT DOCS ---
{context[:1200]}
--- END DOCS ---

Respond with ONLY a JSON object (no markdown, no extra text):
{{
  "product_area": "<one of: {', '.join(valid_areas)}>",
  "request_type": "<one of: {', '.join(REQUEST_TYPES)}>",
  "escalate": <true|false>,
  "escalation_reason": "<short reason if escalate=true, else empty string>"
}}

Rules for escalation (escalate=true):
- Fraud, unauthorized transactions, stolen cards
- Account compromised or hacked
- Legal threats or compliance issues
- Billing disputes involving significant money
- Sensitive personal data exposure
- Issues that require accessing the user's actual account data
- Multi-step issues with no clear answer in the docs

Rules for escalation (escalate=false / reply):
- General how-to questions
- Feature requests
- Documentation-answerable FAQs
- Known bugs with workarounds documented"""

    result = call_llm_json(prompt)

    # Validate and fill defaults
    if result.get("product_area") not in valid_areas:
        result["product_area"] = _heuristic_product_area(issue, company_key)

    if result.get("request_type") not in REQUEST_TYPES:
        result["request_type"] = _heuristic_request_type(issue)

    if "escalate" not in result:
        result["escalate"] = False

    if "escalation_reason" not in result:
        result["escalation_reason"] = ""

    return result


def infer_company(text: str) -> str:
    """
    When company=None, infer which company the ticket belongs to.
    """
    text_lower = text.lower()

    # Strong signals
    if any(w in text_lower for w in ["hackerrank", "coding test", "assessment platform", "hiring assessment"]):
        return "HackerRank"
    if any(w in text_lower for w in ["claude", "anthropic", "claude.ai", "claude api"]):
        return "Claude"
    if any(w in text_lower for w in ["visa card", "visa payment", "visa transaction", "visa debit", "visa credit"]):
        return "Visa"

    # Ask LLM for ambiguous cases
    prompt = f"""A support ticket was submitted without specifying which company it's for.
Determine which of these companies is most likely: HackerRank, Claude (Anthropic), Visa, or Unknown.

Ticket:
{text[:600]}

Respond with ONLY a JSON object:
{{"company": "<HackerRank|Claude|Visa|Unknown>", "confidence": "<high|medium|low>"}}"""

    result = call_llm_json(prompt)
    company = result.get("company", "Unknown")

    if company in ("HackerRank", "Claude", "Visa"):
        return company

    return "Unknown"


# ─────────────────────────────────────────────
# HEURISTIC FALLBACKS
# ─────────────────────────────────────────────
def _heuristic_product_area(text: str, company: str) -> str:
    text = text.lower()

    if company == "hackerrank":
        if any(w in text for w in ["test", "assessment", "challenge", "question"]):
            return "assessments"
        if any(w in text for w in ["payment", "invoice", "bill", "refund"]):
            return "billing"
        if any(w in text for w in ["login", "password", "access", "account"]):
            return "account_access"
        return "general"

    if company == "claude":
        if any(w in text for w in ["api", "sdk", "token"]):
            return "api_access"
        if any(w in text for w in ["payment", "invoice", "bill", "subscription"]):
            return "billing"
        if any(w in text for w in ["login", "password", "account"]):
            return "account_access"
        return "general"

    if company == "visa":
        if any(w in text for w in ["fraud", "unauthorized", "stolen", "dispute"]):
            return "fraud_dispute"
        if any(w in text for w in ["transaction", "payment", "charge"]):
            return "transaction_issue"
        if any(w in text for w in ["activate", "activation"]):
            return "card_activation"
        return "general"

    return "general"


def _heuristic_request_type(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["error", "bug", "crash", "broken", "not working", "failed", "fail"]):
        return "bug"
    if any(w in text for w in ["feature", "add", "would be nice", "suggestion", "improve", "enhancement"]):
        return "feature_request"
    if any(w in text for w in ["spam", "injection", "ignore previous", "disregard", "jailbreak"]):
        return "invalid"
    return "product_issue"
