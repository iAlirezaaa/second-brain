---
name: weekly
description: 20-minute non-negotiable weekly ritual — agent prepares, human decides.
---

# weekly (every Sunday, 20 min, human + agent)

0. **Ask the clock first.** The ritual's cadence is a registry record
   (`11_CONTROL/schedules/SCH-…-weekly-ritual.json`, `every_minutes: 10080`), so
   "weekly" is one definition and not a habit:

   ```
   python scripts/loop.py --due --target skills/weekly/SKILL.md \
     --last-run "$(git log -1 --format=%cI --grep='ritual(weekly)')"
   ```

   Exit 0 = due, exit 3 = a ritual already happened inside seven days (the command
   prints the next window; stop here), exit 1 = the schedule could not be read — fix
   the record, do not guess. An empty `--last-run` (no ritual commit yet) is due.

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
