---
name: elephant-draft
description: Draft a design with the whole context — six cold lenses, a concepts brief, then a design doc a zero-context reviewer can attack. Run it before changing a gate, a zone, a script or a skill.
run_protocol: bounded
---

# elephant-draft

**Law:** the elephant writes; it does not judge what it wrote. Everything produced here is
reviewed by `skills/goldfish-review` in fresh subagent contexts. A draft approved by the mind
that drafted it is not a reviewed draft, it is a memory of a decision.

## 1. Ask before writing (one round, at most six questions)

```
python scripts/memory.py --recall "<the change you are about to design>"
python scripts/health.py
```

Ask the human only what the clone cannot answer: who owns the artifact, what the human types
when a gate refuses, which zone the new files land in, what "done" measures. If
`python scripts/kb.py search "<term>"` or a file read answers it, do not ask — that is the
question that annoys the owner and teaches nothing.

## 2. Six cold lenses, one dispatch each

Each lens is a **fresh subagent** handed the question, the named files and nothing else —
`11_CONTROL/reviewers/egm-explorer.md` is the read-only scout shape (`writes: none`, bounded
reading list). No lens sees another's answer.

| lens | the question, in this repo's words |
|---|---|
| YAGNI | which named artifact would nobody ever open? |
| Cost / quota / tokens | what does one run cost in dispatches, and in doc surface every host must keep in sync? |
| UX / ergonomics | does the human get one command, or a paragraph to decode? |
| Migration / back-compat | which existing record, gate, host door or note breaks when this lands? |
| Observability / SRE | which script refuses when this feature lies, and what does it print? |
| Tech debt | which law is being written into a second place instead of one? |

If the harness has no subagent tool, stop and say it: a review in the same context is not a
Goldfish review (`skills/goldfish-review` carries the condition verbatim). The lens swarm is
the same discipline; a synthesiser that never read the files is summarising a rumour.

## 3. The brief

One synthesiser pass over the six reports writes `90_Agent_Output/briefs/<FEATURE>-concepts-brief.md`:
**Overview / Analysis / Goals vs Non-Goals / Alternatives Weighed / Key Decisions**. Key
Decisions name the alternative that was refused and the law that refused it.

## 4. The design doc

Write `90_Agent_Output/designs/<FEATURE>.md` with the note frontmatter `rules/schema.json`
requires (`id`, `type: note`, `title`, `status: raw`, `owner: agent`, `topics`, `created`,
`updated`), then two headers the reviewer's split rule depends on:

```markdown
## Detailed Implementation Plan        <- the split; above it is the feature range, below it the plan
```

Every plan step names the file it edits, the command that proves it, and the door it goes
through. Structural things (project, skill, agent, note record) never appear before the door:

```
python 15_SYSTEM/scripts/hades.py plan --kind project --name <slug> --description "<what>"
python 15_SYSTEM/scripts/hades.py apply --plan PLAN-<hex> --approve
python scripts/zone_check.py --proposals <proposals.json>
python scripts/write_gate.py --file <draft.md>
```

## 5. Hand it over, then promote

Run `skills/goldfish-review` against the doc path, apply the resolve step, and move only what
the human approves into the human plane (`python scripts/promote.py --proposals ... --item ...`).
A review that changed the design is a decision: record it in `02_WIKI/decisions`.

## Boundaries

- never reviews its own draft, never in this context, never with the conversation as evidence
- no dependency, no network, no server: Python 3.9 standard library or the gate is refused
- nothing lands in `00`-`10` without the approval door; `12_RUNTIME` and `13_LAB` are not evidence
- no typed counts anywhere: `python scripts/doc_report.py --write` owns the numbers

## Output template

`briefs/<FEATURE>-concepts-brief.md` (five sections) + `designs/<FEATURE>.md` (context,
requirements, the design, non-goals, `## Detailed Implementation Plan`) + the doc path you are
about to hand to the goldfish. Stop there; the draft is not the verdict.
