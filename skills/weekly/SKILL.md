---
name: weekly
description: 20-minute non-negotiable weekly ritual — agent prepares, human decides.
---

# weekly (every Sunday, 20 min, human + agent)

1. **Agent preps the draft** `90_Agent_Output/reviews/weekly-YYYY-MM-DD.md`:
   - inbox state (how many captures still unprocessed),
   - notes promoted this week (from `promotions.md`),
   - 3 recurring themes from the week's notes,
   - open questions + connections to older notes,
   - open gaps from `kb.py gaps` worth closing next week.
2. **Human decides, in order:**
   - clear Inbox (approve / archive every capture),
   - archive anything done (`status: archived`),
   - promote 3 next actions,
   - distill **one** note in your own words (AI breadth, brain depth).
3. **Agent closes the loop:** run `health.py`, commit with message
   `ritual(weekly): <date>`.

The person who skips the weekly review gets a graveyard by March — this is the
keystone habit. Twenty minutes.
