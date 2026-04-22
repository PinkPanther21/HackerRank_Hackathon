# Python starter (Python 3.12)

## Setup

```
cd starter/py
python3.12 -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
python agent.py                      # runs against a sample ticket
python ../../tests/run_tests.py --lang py
```

## Contract

Define `solve_ticket(ticket)` in `agent.py`. See AGENTS.md §6.4.
