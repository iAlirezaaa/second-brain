# Protected ideas and architectural change governance

**Policy level:** owner-controlled. Read [GOAL.md](GOAL.md) and [the frozen baseline](../10_ARCHIVE/foundations/README.md).

## Preserve ideas, change implementations

The original vision, founding ideas and specialized concepts are permanent project assets. The improvement loop may evaluate and refactor implementations; it must not silently eliminate a concept because its current implementation is weak or costly.

Frozen snapshots are append-only historical witnesses. **Do not edit, delete, rename, rewrite, auto-format or replace them.** New versions are separate files, linked to the previous version with an explicit decision record. Neither a script argument `--approve`, a prompt, nor an agent-generated sign-off proves a human authorized a protected identity change.

## Mandatory proposal before protected changes

When work touches GOAL, charter/constitution, foundational idea, canonical knowledge semantics, stable IDs, zone ownership, human folder organization, agent permission contracts, model/back-end migration or destructive structure change:

1. **FROM:** exact existing meaning, paths and behavior.
2. **TO:** proposed meaning, paths, behavior and what will cease to work.
3. **WHY:** goal gap, measured evidence, expected gain, alternatives (including no change).
4. **IMPACT:** files, links, commands, external clients, private data, humans, agents, costs and permissions.
5. **VERIFY:** reproducible before/after tests, retrieval correctness, root readability and resource measurements.
6. **RECOVER:** backup, compatibility aliases, reversible migration and rollback proof.
7. **HUMAN DECISION:** explicit owner approval of this exact change (or rejection). **No response = do not proceed.**

Template:

```
Change ID:
Protected idea / GOAL clause:
FROM:
TO:
Why / measured goal gap:
Affected files, users, agents and data:
Alternatives / do nothing:
Expected benefits and tradeoffs:
Evidence and independent tests:
Migration and rollback:
Explicit owner decision: PENDING
```

Unapproved proposals remain in a reviewable branch or candidate shelf, never the trusted goal or core.

## Enforcement status

`scripts/goal_guard.py --check` and CI verify that frozen snapshot content is unchanged and that the permanent GOAL exists; Git history and CODEOWNERS support review. **This is an accidental-drift control, not proof of human identity or cryptographic authorization.** Require branch protection and owner review for actual merge authorization. Do not claim universal enforcement by external harnesses.

## Repository organization

Keep GitHub itself navigable. Existing numbered zones remain the current placement contract. Audit references/tests before moving a root file; retain stable entrypoints and external compatibility, and report any root clutter honestly. A documented folder alone is not a functional index.
