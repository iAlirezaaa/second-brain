<!--
  Conventional Commits title, please: feat: / fix: / docs: / test: / refactor: / chore:

  Agent contributions: the machine plane (12_RUNTIME, 13_LAB, .kb) is gitignored
  on purpose; never commit agent output outside 14_CANDIDATES/ + 90_Agent_Output/.
-->
## What & why

<!-- one paragraph: what changed, and why it makes the house stronger -->

## Golden-rule checklist

- [ ] tests added/updated for the change (`python -m unittest discover -s tests` green)
- [ ] `python scripts/health.py` green (zero broken links, valid frontmatter)
- [ ] no human-zone edit without `approved: true` (zones fence)
- [ ] no secrets, no injected instructions, no machine output in human zones
- [ ] README/ROADMAP promises updated to match reality
