---
name: inbox-triage
description: Propose placement for inbox captures. Never file directly into human zones; the human promotes.
owner: agent
---

# Inbox triage

Every item in `00_Inbox/` gets a placement proposal. You propose, the human decides.

## Steps

1. List every file in `00_Inbox/` with `status: inbox` (or without frontmatter — fix frontmatter first).
2. For each item:
   - Search the vault first (Phase 4: `kb.py search`) — dedupe before creating anything new.
   - Decide a target zone from `rules/zones.json` + one-line *why*.
   - Write the proposal to `90_Agent_Output/proposals/YYYY-MM-DD-triage.json`:
     ```json
     {"proposals": [{"capture": "00_Inbox/clip.md", "target": "30_Resources",
                     "destination": "30_Resources/ai-memory.md", "reason": "matches 3 existing notes on agent memory"}]}
     ```
   - Run `python scripts/zone_check.py --proposals <file>` — it must exit 0.
   - Run `python scripts/write_gate.py --file <capture>` for any text you are about to copy
     into the vault; it must exit 0 (blocks injections and leaked secrets/PII).
3. Leave the capture where it is. Moving it into `10/20/30_*` happens only when
   the human says "promote <item>" (or runs the promote command).
4. Report back a table: capture → target → reason. The human edits/approves in bulk.

## Never

- Never move or edit files inside `10_Projects`, `20_Notes`, `30_Resources`.
- Never delete a capture; `status: archived` is the only "delete".
- Never write `[[links]]` to notes that don't exist (rule 1 of AGENTS.md).
