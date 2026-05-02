"""
llm.py
======
Wrapper around the Groq API using the official groq SDK.
(Raw urllib calls get blocked by Cloudflare with error 1010 — SDK fixes this.)

Get your FREE API key:
  1. https://console.groq.com  →  Sign up  →  API Keys  →  Create
  2. export GROQ_API_KEY=gsk_...
     OR put  GROQ_API_KEY=gsk_...  in  code/.env

Free tier: 14,400 req/day, 30 req/min on llama-3.3-70b
~30 tickets × 2 calls = 60 calls total — well within limits.
"""

import os
import time
import json
from pathlib import Path


# ── Models ────────────────────────────────────────────────────────────────────
MODEL          = "llama-3.3-70b-versatile"   # best free model on Groq
FALLBACK_MODEL = "llama-3.1-8b-instant"      # faster fallback
MAX_RETRIES    = 3
RETRY_DELAY    = 5.0


def _load_api_key() -> str:
    """Load GROQ_API_KEY from env var or code/.env file."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key

    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _get_client():
    """Create a Groq client instance."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed.\n"
            "Run:  pip install groq"
        )

    api_key = _load_api_key()
    if not api_key:
        raise EnvironmentError(
            "\nGROQ_API_KEY not found!\n"
            "  1. https://console.groq.com  →  API Keys  →  Create  (free)\n"
            "  2. export GROQ_API_KEY=gsk_...\n"
            "     OR add  GROQ_API_KEY=gsk_...  to  code/.env\n"
        )

    return Groq(api_key=api_key)


def call_llm(
    prompt: str,
    system: str = "You are a helpful, concise support agent.",
    max_tokens: int = 600,
    temperature: float = 0.2,
    use_fallback: bool = False,
) -> str:
    """Call Groq and return the response text. Retries on rate limits."""
    client = _get_client()
    model  = FALLBACK_MODEL if use_fallback else MODEL

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            err_str = str(e).lower()

            # Rate limited
            if "429" in str(e) or "rate limit" in err_str:
                wait = RETRY_DELAY * attempt
                print(f"  ⏳ Rate limited. Waiting {wait}s "
                      f"(attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)

            # Wrong model name / model not available
            elif "model" in err_str and not use_fallback:
                print(f"  ⚠  Model {model} unavailable, "
                      f"switching to {FALLBACK_MODEL}...")
                return call_llm(
                    prompt, system, max_tokens, temperature, use_fallback=True
                )

            # Transient server error
            elif attempt < MAX_RETRIES:
                print(f"  ⚠  LLM error ({e}). "
                      f"Retrying ({attempt}/{MAX_RETRIES})...")
                time.sleep(RETRY_DELAY)

            else:
                raise

    raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts.")


def call_llm_json(
    prompt: str,
    system: str = (
        "You are a support triage classifier. "
        "Respond ONLY with a valid JSON object. "
        "No markdown, no backticks, no explanation — just the JSON."
    ),
    max_tokens: int = 400,
) -> dict:
    """Call LLM and parse the response as JSON."""
    raw = call_llm(prompt, system=system, max_tokens=max_tokens, temperature=0.0)

    # Strip markdown fences if the model ignores instructions
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Best-effort: extract outermost { ... }
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    return {}
