# Repository structure — ownership, placement and migration rules

**Status:** operative placement map. Do not treat empty directories as product functionality.

## One owner for every kind of record

| Area | Content authority | Allowed examples |
| --- | --- | --- |
| `00_START_HERE/` | Maintainers / human | Product charter, architecture, quickstarts, English docs; a separate Persian translation file |
| `01_INBOX/` | Human intake | Incoming captures before classification |
| `02_WIKI/` | Human knowledge | Reviewed notes, concepts, references, decisions |
| `03_PROJECTS/` | Human project manager | Stable project IDs, status and source-of-truth project records |
| `04_INTELLIGENCE/` | Human research | Research evidence, model comparisons, benchmark reports |
| `05_WORKS/` | Human creative/workflow owner | Deliverables, workflows, materials |
| `06_CHANNELS/` | Human publishing owner | Editorial plans, channel metadata, performance |
| `07_PRODUCTS/` | Human product owner | App/extension/game product specs |
| `08_LEARNING/` | Human learning owner | Courses, exercises, distilled learning |
| `09_OPERATIONS/` | Human operator | Decisions, incidents, operational records; no raw credentials |
| `10_ARCHIVE/` | Human curator | Explicitly retired, searchable versions |
| `11_CONTROL/` | Reviewed registry | Agents, tools, schedules, approved skills and policy records |
| `12_RUNTIME/` | Local-only actor runtime | Generated runs and volatile runtime data (gitignored) |
| `13_LAB/` | Local-only experiments | Discardable prototypes, fixtures, cached simulation state |
| `14_CANDIDATES/` | Quarantine/review ledger | Proposed changes with evidence; not live permissions or canonical Skills |
| `15_SYSTEM/` | Core maintainers | Engine, storage contracts, source ingestion, MCP adapters |
| `scripts/` | CLI and checks | Stable human-facing commands and one-shot utilities |
| `skills/` | Reviewed Skill owners | `SKILL.md` packages, metadata-first discovery and versioned tests |
| `tests/` | Independent evaluation | Regression, safety, golden datasets; no personal data |
| `rules/` | Governance | Machine-validated schemas and placement rules |
| `vault-template/` | Example data | Minimal distributable template, not a personal vault |

## Why there are two script directories

`scripts/` is the stable **public command surface**: checks, installation,
backup, CLI and operator workflows. `15_SYSTEM/scripts/` is the **engine
implementation** and command wrappers for the HADES registry, MCP, workflows
and local memory backend. These are separate intentionally.

Moving either directory without a compatibility strategy breaks imports,
AGENTS.md entrypoints, host-generated instructions and external clients.
Keep the stable paths while consolidating duplicate functionality by
introducing shared, tested libraries behind those interfaces.

## File identity and migration

1. Each project, agent, workflow and skill uses a stable identifier in its
   registered JSON/Markdown frontmatter; filenames are display paths, not identities.
2. A canonical record is stored only once. Indexes, topic lists, search caches
   and graph views are derived and may be rebuilt.
3. Keep personal state in ignored private stores. Never attach a password,
   token, health record or entire conversation to a public issue.
4. A move requires an inventory of inbound links, exact file fingerprint,
   updated references, old-path compatibility or explicit migration, tests
   and a rollback plan.
5. Automated reorganization is a **proposal/dry-run** first. Do not move
   hundreds of files merely to make the tree look uniform.
6. Generated artifacts remain outside human-owned zones unless the user
   approves promotion. Review candidates live on their own shelf.
7. Empty template folders are not evidence of a working subsystem; the
   README states operational capability independently from folder presence.
8. Only owner-reviewed skill proposals are admitted to canonical `skills/`.

## Current recommended cleanup order

- P0: make health checks fail closed, fix the nightly reporting workflow,
  and remove inaccurate status/translation duplication from README.
- P1: inventory duplicate CLI and engine responsibilities, fix broken links
  and metadata references, and gate generated-output destinations.
- P2: split engine into importable modules while keeping existing CLI paths
  as backwards-compatible shims.
- P3: after reference inventory and restore tests, move or archive obsolete
  drafts and duplicate documentation. Preserve stable IDs.

See [System map](SYSTEM_MAP.md), [Charter](PROJECT_CHARTER.md),
[Agent rules](../AGENTS.md) and [Architecture vision](PRODUCT_VNEXT.md).

**Verification rule:** a red gate is not solved by removing the check or
rewriting a claim until it agrees with itself.
