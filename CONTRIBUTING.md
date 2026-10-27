# Contributing — second-brain

Thanks for considering a contribution. This repo is a plain-markdown vault a human
curates and AI agents maintain — its core discipline is **every rule is a script, not a
suggestion**. Contributions that follow that discipline are welcome.

## Setup

```bash
git clone https://github.com/iAlirezaaa/second-brain.git
cd second-brain
python -m unittest discover -s tests   # everything green = healthy workspace
python scripts/health.py               # vault integrity check
```

Python ≥ 3.9, no pip dependencies. All engine scripts stay **stdlib-only**.

## The rules that govern contributions

1. **Zero broken links** — `[[wikilinks]]` must resolve; run `python scripts/link_check.py`.
2. **Fenced zones** — never edit a human zone without approval (see `vault-template/AGENTS.md`
   and `rules/zones.json`).
3. **Nothing is ingested until it is linked.**
4. **Machine output goes to the machine plane** — agent/loop artifacts live in
   `14_CANDIDATES/` (crawl-shelf) or `90_Agent_Output/`, never in `20_Notes/`.
5. **Every feature ships with a test first** — if you add a script or a skill, the
   same PR must contain its unittest coverage; CI runs the full suite on every PR.

## What a good PR looks like

- title follows Conventional Commits (`feat:`, `fix:`, `docs:`, `test:` …)
- small and focused; each PR = one idea
- includes tests, and the README/ROADMAP lines it promises are ticked off
- states in the PR template that you ran the full test suite

## Bilingual note

The user-facing docs are English + Persian (فارسی). If you change user-facing
behavior, updating **either** language suffices in a PR — maintainers will help keep
both halves in sync.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
