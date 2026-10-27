# Index — the ground map

Both a human and an agent land here. Two minutes, either direction.

## What you are looking at

A knowledge base of linked markdown pages. Raw material goes to
`00_Inbox/`; the agent triages it into typed zones; what you *think* lives in
`20_Notes/`; reference material in `30_Resources/`; the agent's own work in
`90_Agent_Output/`.

## Zones

- `00_Inbox/` — everything unprocessed. Empty it once a week.
- `10_Projects/` — active work with a finish line. One folder each (soon).
- `20_Notes/` — distilled thinking in your own words. Human-authored, human-owned.
- `30_Resources/` — reference by topic.
- `90_Agent_Output/` — the agent's zones: sessions, reviews, postmortems.

## How to find things

- Ask the agent, in conversation: "what have I captured about X?"
- Or search keywords: `python scripts/kb.py search "X"` (Phase 4).
- Health: `python scripts/vault_stats.py`.

## State of the house

- Zero broken links is the law — see `AGENTS.md` rule 1.
- `status` lifecycle: `inbox → raw → refined → evergreen`.
- `owner` on every note: `human` or `agent`. The agent never edits `owner: human` files.
