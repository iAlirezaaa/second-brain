---
name: promote
description: The single command that moves an approved capture from Inbox into the human-owned vault.
human_run: true
---

# promote

Run by the human (or by the agent *after* the human explicitly approved the item).
Reads a triage proposal and executes it safely.

```
python scripts/promote.py --proposals 90_Agent_Output/proposals/2026-01-01-triage.json --item 00_Inbox/clip.md
```

## What it does

1. Finds the proposal for `--item` in the proposals file.
2. Refuses if the target zone is human-owned and the item was not approved.
3. Moves the file (git mv when in a repo), updates frontmatter:
   `status: inbox → raw`,
   rewrites `id` for the new location, appends `promoted_by: human, promoted_on: <date>`.
4. Runs the zero-broken-links check — your vault never goes red.
5. Appends a line to `90_Agent_Output/proposals/promotions.md` (the audit trail).
