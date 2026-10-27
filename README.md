# second-brain

An AI-augmented second brain: a plain-markdown vault that a human curates and AI agents maintain.

- **Plain markdown you own** — Obsidian-compatible (`[[wikilinks]]`, frontmatter). No database, no lock-in.
- **Fenced zones** — the agent writes freely only in its zones; your notes (`20_Notes`) need approval.
- **Integrity toolchain** — zero broken links, validated frontmatter, vault stats. Every rule is a script, not a suggestion.
- **Skills, not prompts** — each workflow is a written protocol an agent can follow deterministically.

See [ROADMAP.md](ROADMAP.md) for the build plan and status.

## Quickstart

```bash
git clone https://github.com/iAlirezaaa/second-brain.git
cd second-brain
python -m unittest discover -s tests -v   # everything green = vault is healthy
```

Open `vault-template/` as an Obsidian vault, and point your agent (Claude Code / OpenCode) at the repo — it reads `AGENTS.md` first.

## The two audiences

| You (human) | Your agent |
|---|---|
| Reads `index.md`, browses MOC-style map | Reads `AGENTS.md` + `rules/zones.json` on session start |
| Curates `20_Notes`, makes judgment calls | Triages `00_Inbox`, proposes placements with a one-line why |
| Writes rules, audits diffs in git | Writes freely in `90_Agent_Output`, never edits `20_Notes` |

## License

MIT
