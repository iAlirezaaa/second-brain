---
name: kb-search
description: Search-first protocol — an agent must search the KB before reading files and before creating any note (dedupe + links).
owner: agent
---

# kb-search

Search before you act. Two moments are mandatory:

1. **Before reading many files** — `python scripts/kb.py search "topic"` first;
   read only the hits (context budget).
2. **Before creating any note** — search the topic and its synonyms. If a note
   already exists, extend it instead of duplicating it. If search returns **no
   hits**, log it: `python scripts/kb.py gap "query"` — this registers the gap
   in the house backlog (view with `kb.py gaps`).

## Ground rules

- Prefer `kb.py ingest` after big edits so the index stays fresh.
- Cite paths in your answer (the agent reading after you needs receipts).
- No secrets into the index: run write_gate on anything suspicious before ingest.
