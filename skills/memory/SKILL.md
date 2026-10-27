---
name: memory
description: Read and write the repo's own memory — recall a lesson before acting, record one with evidence after being wrong, supersede instead of deleting.
---

# memory

The design lives in `15_SYSTEM/memory/README.md`; this is the procedure. Two rules explain
everything else: a lesson without evidence is a preference, and a memory nobody can read is
a diary.

## Recall — before you start, not after you fail

```
python scripts/memory.py --recall "probe says stale after I edited the file"
python scripts/memory.py --recall "the gate passed with no output" --json
```

Ordered by word overlap, then confidence. Take the top row as a hypothesis with a citation,
not as an oracle: open its `evidence` and check the claim is still true today. If nothing
matches you get `NO_ENTRY` and exit 0 — record that as data, do not pad an answer.

## Record — only something that changed what you would do next time

```
python scripts/memory.py --add \
  --id mem-child-output-encoding \
  --cue "a gate passed but printed nothing" \
  --lesson "read the child as UTF-8; encoding is stated, not inherited" \
  --evidence scripts/common.py,HANDOFF.md \
  --confidence 0.9 --verdict helped \
  --source "chat 2026-10-27"
```

The gate refuses the common shortcuts: no evidence, evidence that does not open, a duplicate
id, a verdict outside the vocabulary, a confidence outside 0..1, a non-numeric confidence.
Every refusal prints a reason and writes nothing — a half-recorded lesson is worse than none,
because the next agent will trust it.

`--supersedes mem-old` retires a belief. The old row stays in the ledger and shows up under
"Retired" in `MEMORY.md`: the record of a wrong belief is what stops you re-adopting it.

## Render and check

```
python scripts/memory.py --render
python scripts/memory.py --check        # health.py runs this as its fourth gate
python scripts/memory.py --list
```

`MEMORY.md` is generated — hand-editing it is drift, and `--check` fails the build in both
directions (an active lesson the index hides, an id in the index the ledger never held).

## When a lesson is really a change to the machinery

Do not write prose about it: write a candidate row on `14_CANDIDATES/loop/` with
`dimension: invariant`, run `scripts/probe.py`, and let `promote` be the thing that changes
the rule. Memory records what was learned; the shelf is where a learned thing becomes law.
