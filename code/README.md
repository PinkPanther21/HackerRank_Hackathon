# Multi-Domain Support Triage Agent

A terminal-based support triage agent for HackerRank, Claude (Anthropic), and Visa support tickets.

## Architecture

```
support_tickets.csv
        │
        ▼
┌───────────────────┐
│   safety.py       │  ← Prompt injection / abuse detection (runs FIRST)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   classifier.py   │  ← Infers company (if None), classifies ticket via LLM
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   retriever.py    │  ← Semantic search over .md corpus (sentence-transformers)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   llm.py          │  ← Grok API (Free): generates grounded response
└────────┬──────────┘
         │
         ▼
    output.csv
```

## Key Improvements Over Baseline

| Feature | Baseline | This Agent |
|---|---|---|
| Classification | Keyword matching | LLM-based with structured JSON |
| Response generation | Raw doc dump | Grounded LLM response |
| Escalation logic | `fraud`/`hack` keywords only | Hard + soft triggers + LLM judgment |
| Safety | None | Prompt injection + abuse detection |
| Company inference | Not implemented | LLM + heuristics |
| Justification | Static string | Dynamic per-ticket explanation |
| Chunking | Whole doc (500 char truncation) | Overlapping paragraph chunks |
| Product area taxonomy | 3 vague areas | 10+ per-company areas |
| Multi-request tickets | Not handled | Single LLM pass handles all |
| Fallback retrieval | None | Cross-corpus fallback |

## Setup

```bash
# 1. Install dependencies
pip install sentence-transformers numpy

# 2. Set your Gemini API key (Free)
export GROK_API_KEY=your-api-key


# 3. Ensure data directory structure:
#    data/
#      hackerrank/   ← .md files scraped from support.hackerrank.com
#      claude/       ← .md files scraped from support.claude.com
#      visa/         ← .md files scraped from visa.co.in/support

# 4. Run on sample tickets (to verify)
python agent.py --sample

# 5. Run on actual tickets
python agent.py

# Options
python agent.py --input path/to/support_tickets.csv --output path/to/output.csv
python agent.py --limit 10    # process only first 10 (testing)
```

## File Structure

```
agent/
├── agent.py          # Main entry point
├── retriever.py      # Document loading + semantic search
├── classifier.py     # LLM-based ticket classification
├── llm.py            # Grok API wrapper
├── safety.py         # Prompt injection + abuse detection
└── requirements.txt

data/
├── hackerrank/       # .md support docs
├── claude/           # .md support docs
└── visa/             # .md support docs

support_tickets/
├── support_tickets.csv       # Input
├── sample_support_tickets.csv
└── output.csv                # Generated output
```

## Output Schema

| Field | Values | Description |
|---|---|---|
| `status` | `replied` / `escalated` | Whether the agent answered or routed to human |
| `product_area` | company-specific taxonomy | Best-fit support category |
| `response` | string | User-facing answer grounded in corpus |
| `justification` | string | Explanation of routing decision |
| `request_type` | `product_issue` / `feature_request` / `bug` / `invalid` | Ticket classification |

## Escalation Logic

**Always escalate:**
- Fraud, unauthorized transactions, stolen cards
- Compromised/hacked accounts  
- Legal threats or compliance issues
- Prompt injection attempts

**Conditionally escalate:**
- Billing disputes (refunds, overcharges)
- Account lockouts
- Data breach concerns
- Issues with no corpus coverage

**Reply directly:**
- How-to questions answerable from docs
- Feature requests (acknowledge + document)
- Known bugs with documented workarounds
- General FAQs
