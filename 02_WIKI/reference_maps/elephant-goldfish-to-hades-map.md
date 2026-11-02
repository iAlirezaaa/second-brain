---
id: map-elephant-goldfish-to-hades
type: resource
title: "elephant-goldfish-model → HADES: what to adopt, what to refuse, and why"
status: evergreen
owner: agent
topics: [architecture, review, agents, harness, gate]
created: 2026-11-02
updated: 2026-11-02
---

# elephant-goldfish-model → HADES map

Reverse-engineering note for [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model):
a Claude-Code-plugin discipline in which an **elephant** (the context-rich agent that drafted a
specification) is reviewed by **goldfish** (zero-context subagents that never saw the drafting
conversation). Its five stages — `zoom-out`, `comprehension`, `critic`, `intermediate-zoom-out`,
`implementation-readiness` — are dispatched by a review loop with a convergence rule, and a
resolve step hands the findings back to a human gate. Facts below are its mechanics as inventoried
from that repo; nothing here installs from it.

## The verdict in one sentence

EGM's plugin packaging (manifests, a marketplace, harness-specific frontmatter, slash commands)
is **refused**; its discipline — draft cold, review colder, and make the review an artifact a
script can refuse — is **adopted**, because a repo whose canon is read by six harnesses before
they act has exactly EGM's problem: the agent that wrote the design is the agent that would
otherwise approve it.

## Adoption table

| EGM concept | What it actually is there | Verdict in HADES | Where it lands here |
|---|---|---|---|
| Plugin manifest + marketplace install | packaged third-party code you install | **refuse** — no dependency, no network, no install step; a capability is a script plus a skill the repo already ships | `11_CONTROL/plugins` stays empty by design; `scripts/install.py` copies tracked files only |
| Harness-specific frontmatter (`.claude/`, per-tool keys) | one dialect per host | **refuse** — one canon, six generated pointers | `scripts/sync_hosts.py` (gated by `--check`) |
| Slash commands `/egm-review`, `/egm-bootstrap`, `/egm-drift-report` | a command surface inside one app | **refused as commands, adopted as skills + doors** — this repo speaks `python scripts/<gate>.py` and `skills/<name>/SKILL.md` | `skills/goldfish-review`, `skills/elephant-draft`, `skills/drift-report` |
| Elephant role | project + requirements + all earlier decisions; explores and drafts | **adopted** | `skills/elephant-draft/SKILL.md` |
| Goldfish role | the document and its cited sources, no conversation; hunts missing assumptions, unclear requirements, implementation risks | **adopted, as data** — 8 personae, each with its own stage, range, audit vectors and bounded reading list | `11_CONTROL/reviewers/egm-*.md` |
| Three universal mandates | strict read-only, stateless isolation, no chitchat | **adopted and enforced** — `goldfish_check.py --personas` refuses a persona missing one, or one that declares a write tool | `scripts/goldfish_check.py`, `tests/test_phase43_goldfish_method.py` |
| Verbatim stop condition: no subagent tool ⇒ no goldfish review | the honest failure mode of the whole idea | **adopted verbatim** — "If your harness has no subagent tool, stop and tell the user: a review in the same context is not a Goldfish review." It is in every skill this phase ships and in every refusal naming `context: shared` | `skills/goldfish-review/SKILL.md`, `scripts/goldfish_check.py` (`STOP_CONDITION`) |
| Workflow order: brainstorm → brief → draft → design doc → review → resolve → implement → drift | the shape of the loop | **adopted, re-pathed** — `docs/designs/` is refused; the human plane's zones and the approval door own the destination | `skills/elephant-draft` §3-§5, `03_PROJECTS`, `90_Agent_Output` |
| Five stages, in order | zoom-out / comprehension / critic / intermediate zoom-out / implementation readiness | **adopted**; a report that claims a stage no persona covers is refused | `scripts/goldfish_check.py` (`STAGES`, `REQUIRED_STAGES`) |
| Comprehension spawned **directly**, opening with two verbatim paraphrase headings | the anti-summary safeguard | **adopted** — the two headings are checked in the artifact, the persona must declare `spawn: direct`, and a recorded stage with no reviewer row is refused | `scripts/goldfish_check.py` (`COMPREHENSION_HEADINGS`, `SPAWN_MODES`) |
| The semantic split (`## Detailed Implementation Plan` + synonyms) | feature range vs implementation range | **adopted**; stage 9 over a document with no such header is a refusal, so a range cannot be imagined | `scripts/goldfish_check.py` (`SPLIT_HEADERS`) |
| Review-loop driver: re-resolve the target, hierarchical or flat dispatch | the scheduling of the swarm | **adopted**; the target's line ranges are re-checked against the document's real length | `scripts/goldfish_check.py` (`## Target` rules) |
| Severities 🔴/🟡/🟢 + stable ids `<reviewer>-<round>-<n>` | findings that survive a re-run | **adopted**; an id that moves between rounds is refused, an id with two statuses is refused | `scripts/goldfish_check.py` (`norm_severity`, id regex) |
| Failed-reviewer rule | "a reviewer that returns no report did not review; never count it as zero findings" | **adopted, gated** — a `run` row with no report file is refused, and `not_run` makes the round dirty | `scripts/goldfish_check.py` |
| Clean round / CONVERGED (two consecutive) / CAP 5 / CHURN | convergence, so the loop terminates | **adopted** — `clean: yes` is derived from the roster and the findings, never granted by the column | `scripts/goldfish_check.py` (`ROUNDS_CAP`) |
| Resolve categories CONTEST / ESCALATE / PROPOSE FIX / DECLINE (+3 rules) | the elephant's answer, not a silent edit | **adopted** — a contest must cite a `file[:symbol]` that opens; `escalate` must be `escalated`; `decline` is a nit answer | `skills/goldfish-review` §Resolve |
| Human gate: auto-accept / continue / interactive / comment / custom | the owner decides | **already the repo's law** — agents propose, humans decide; the door is `--approve` | `scripts/promote.py`, `scripts/zone_check.py`, `hades.py apply --approve` |
| 6-lens brainstorm swarm (YAGNI / cost / UX / migration / observability / tech debt) | the pre-draft argument | **adopted, translated to this repo's constraints**: stdlib-only, no server, gate-enforceability, clone-readable evidence, the approval door, doc-surface cost | `skills/elephant-draft` §2 |
| `concepts_brief.md` (Overview / Analysis / Goals vs Non-Goals / Alternatives Weighed / Key Decisions) | what the swarm compiles to | **adopted** | `skills/elephant-draft` §3 |
| Accepted trade-offs (residuals after the cap) | what the loop could not settle | **adopted** — a residual finding absent from that section is refused | `scripts/goldfish_check.py` (`## Accepted trade-offs`) |
| `/egm-bootstrap`: generate docs bottom-up, safety gate past 15 dirs, read-only scout | cold documentation of a tree | **partly adopted** — the scout and its safety gate are real; mass doc generation stays a human call | `11_CONTROL/reviewers/egm-explorer.md`, `scripts/goldfish_check.py` (`SCOUT_LIMIT`) |
| `/egm-drift-report`: checked-in documents vs current source | the second half of the discipline | **adopted** — a drift row must name a document that really contains the citation, so a report cannot invent a defect | `skills/drift-report/SKILL.md`, `goldfish_check.py` (`judge_drift`) |
| EGM's own plugin tests / CI | proof for that packaging | **refused, replaced** — the artifact is judged, not the claim | `tests/test_phase43_goldfish_method.py` |

## Where each adopted piece lives (script + test)

| piece | script | data | test |
|---|---|---|---|
| the drafting discipline (questions, 6-lens swarm, brief, design doc, the split header) | a skill, not a script: `skills/elephant-draft/SKILL.md` | the six lenses are named in the skill | `tests/test_phase43_goldfish_method.py::TheDraftingSkills` |
| the review discipline (stages, loop rules, resolve) | `skills/goldfish-review/SKILL.md` | 8 personae in `11_CONTROL/reviewers/` | `tests/test_phase43_goldfish_method.py::TheGateJudgesTheArtifact` |
| the drift discipline | `skills/drift-report/SKILL.md` | `11_CONTROL/reviewers/egm-explorer.md` | `tests/test_phase43_goldfish_method.py::TheDriftReportIsRechecked` |
| the judge | `scripts/goldfish_check.py` (`--report`, `--drift`, `--personas`, `--self-test`) | `rules/schema.json` for the note contract, `scripts/common.py` for `clone_readable` | `python scripts/goldfish_check.py --self-test` (12 cases: the honest artifacts pass, and the four lies this phase names are refused) |

## Not wired into `health.py`, on purpose

`scripts/health.py` counts its own gate list (`doc_report.py` measures it into `README.md`,
`HANDOFF.md` and `00_START_HERE/START.md`), and those three files are owned by the commit step,
not by this map: a tenth entry there moves a measured number in documents this phase may not
edit. So `goldfish_check.py` ships as its own door:

```
python scripts/goldfish_check.py --self-test      # proves the refusals fire
python scripts/goldfish_check.py --personas       # the reviewer set is a goldfish set
python scripts/goldfish_check.py                  # personae + every review and drift report in the clone
python scripts/goldfish_check.py --report <path>  # one report
```

Promoting it is one appended entry in `GATES` (and one in `ROOT_ONLY_GATES`) of
`scripts/health.py` —
and `python scripts/doc_report.py --write` in the same commit, or the gate count in the documents
stops being a measurement. Its no-argument mode is already health-shaped: one `OK` line, exit 1 on
any refusal, exit 2 when it could not read the artifact.

## The registration door the human opens

Every `skills/*/SKILL.md` in the pack must also exist as a registry record, or no host can find it
— `tests/test_phase17_control_plane.py::TestRegisteredSkills::test_every_skill_in_the_pack_is_a_registry_record`
is red for exactly as long as a body has no record. Records are written by the door, never by hand,
and the door needs the human's `--approve`; this map therefore ships the three bodies and stops at
the threshold:

```
python 15_SYSTEM/scripts/hades.py plan --kind skill --name elephant-draft --description "<what it does>"
python 15_SYSTEM/scripts/hades.py plan --kind skill --name goldfish-review --description "<what it does>"
python 15_SYSTEM/scripts/hades.py plan --kind skill --name drift-report --description "<what it does>"
python 15_SYSTEM/scripts/hades.py apply --plan PLAN-<hex> --approve   # one per plan
```

The shape each record lands in is `11_CONTROL/skills/SKL-<hex8>-<name>/skill.json` with
`entrypoint: skills/<name>/SKILL.md` — see `11_CONTROL/skills/SKL-A46425EE-health/skill.json`.
A `SKL-` record is registry-shaped (`id` + `kind`), which is why the reviewer definitions in
`11_CONTROL/reviewers/` are deliberately **not** records: they are dispatched by a harness, not
resolved by the registry.

## Final folder structure — answer

No new top-level zone; the machine plane gains one folder of definitions and the script plane one
gate:

```
02_WIKI/reference_maps/         + this map
11_CONTROL/reviewers/           + egm-{zoom-out,comprehension,design,structural,style,
                                  codebase-details,implementation-readiness,explorer}.md
scripts/                        + goldfish_check.py
skills/                         + elephant-draft/ goldfish-review/ drift-report/ (SKILL.md each)
tests/                          + test_phase43_goldfish_method.py
```

`00`–`10` and `15_SYSTEM` are untouched; `11_CONTROL/agents` and `11_CONTROL/skills` are untouched
(the registry records for the new skills go through `hades.py plan` → `apply --approve`, which is
the owner's door, not a hand-written JSON file); `rules/*` and `15_SYSTEM/config/system.json` are
untouched, so no new kind and no new status vocabulary entered the contract. The reviewer files
carry a note-shaped `id` and **no `kind`**, which is what keeps them definitions-with-a-body
rather than ghost registry records — the phase-21 law.
