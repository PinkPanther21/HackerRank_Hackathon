"""
safety.py
=========
Detects prompt injection attempts, malicious inputs, and abuse
before any LLM processing occurs.
"""

import re


# ─────────────────────────────────────────────
# INJECTION PATTERNS
# ─────────────────────────────────────────────
INJECTION_PATTERNS = [
    # Classic prompt injection
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+",
    r"forget\s+(everything|all|your)\s+",
    r"new\s+instruction[s]?[:\-]",
    r"system\s*prompt[:\-]",
    r"you\s+are\s+now\s+a?\s*(new\s+)?(ai|bot|assistant|gpt)",
    r"\bDAN\b",
    r"jailbreak",
    r"pretend\s+you\s+(are|have\s+no)",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(an?\s+)?(evil|uncensored|unfiltered)",
    r"bypass\s+(your\s+)?(safety|filter|restriction|guideline)",
    # Attempting to extract system prompts
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"reveal\s+(your\s+)?(instructions?|system\s+prompt)",
    r"what\s+(is\s+your\s+|are\s+your\s+)(system\s+prompt|instructions?)",
    # Role-switching
    r"you\s+are\s+(no\s+longer|not)\s+a\s+support",
    r"switch\s+to\s+(developer|admin|root)\s+mode",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


# ─────────────────────────────────────────────
# ABUSE SIGNALS
# ─────────────────────────────────────────────
ABUSE_KEYWORDS = [
    "create malware", "write a virus", "hack into", "how to hack",
    "exploit vulnerability", "sql injection", "xss attack",
    "bomb", "weapon", "poison", "explosive",
]


def safety_check(text: str) -> dict:
    """
    Returns {"flagged": bool, "reason": str}.
    Checks for prompt injection and clearly abusive content.
    """
    # 1. Prompt injection
    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            return {
                "flagged": True,
                "reason":  f"Prompt injection attempt detected: '{match.group()}'",
            }

    # 2. Abuse / off-topic harmful content
    text_lower = text.lower()
    for kw in ABUSE_KEYWORDS:
        if kw in text_lower:
            return {
                "flagged": True,
                "reason":  f"Potentially harmful content detected: '{kw}'",
            }

    # 3. Excessively long (possible DoS or data exfil attempt)
    if len(text) > 8000:
        return {
            "flagged": True,
            "reason":  "Input exceeds maximum allowed length (8000 chars).",
        }

    return {"flagged": False, "reason": ""}
