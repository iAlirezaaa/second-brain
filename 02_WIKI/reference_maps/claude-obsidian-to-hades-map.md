---
id: map-claude-obsidian-to-hades
type: resource
title: "claude-obsidian → HADES: what to adopt, what to refuse, and why"
status: evergreen
owner: agent
topics: [knowledge-management, agents, provenance, privacy, harness, structure]
created: 2026-11-02
updated: 2026-11-02
---

# claude-obsidian → HADES map

Reverse-engineering note for [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian),
named as **reference one** in `00_START_HERE/PROJECT_CHARTER.md` §3, which asks for five lenses on
it — knowledge management, memory, information structuring, the links between files, and how
agents actually operate — and then sets the limit itself: extract the useful logic and generalize
it to **every** agent, because "the system must not be limited to Claude or Obsidian".

What upstream *is*, stated from its own README (read 2026-11-02; MIT, v3.0.1, ~16k stars): a
"self-organizing AI second brain for Obsidian + Claude Code", shipped as a Claude Code plugin and
as Agent Skills for other hosts, "based on Karpathy's LLM Wiki pattern". Its shape is 15 skills
plus 3 read-only agents (`wiki-ingest`, `wiki-lint`, `verifier`) behind one writing layer —
"only one place, the transaction core, ever writes to your vault" — with a CLI at
`scripts/claude-obsidian.py` (`doctor`, `init`, `adopt`, `lint`, `capture`, `transaction recover`,
`bench`) and contracts in `skills/wiki/references/operation-transactions.md` and
`skills/wiki/references/provenance.md`. Its transaction spec is "one plan, one apply": each note
carries a SHA-256 fingerprint, a journal makes `transaction recover` possible after an
interruption, and a concurrent edit raises "a conflict instead of overwriting you". Sources land
in `inbox/` as untouched content-addressed originals; retrieval is "local BM25 search with
optional reranking"; `wiki-lint` reports "dead links, orphan pages and gaps"; the stance is "no
cloud database, no lock-in, no telemetry", with web research and remote models "off until you
allow them".

What HADES did with that is in this repo's tracked text, not in a chat log:
the lesson row `mem-doors-must-point-at-real-rooms` in `15_SYSTEM/memory/lessons.jsonl` names its
`source` as "porting claude-obsidian agent-at-work behaviour to every host", and
`02_WIKI/reference_maps/eight-memory-planes.md` is the same paper's structure — one row per thing,
with writer, reader and proof — turned into a gate.

## The verdict in one sentence

claude-obsidian is a **plugin that respects a vault**; HADES wants a **vault that no plugin owns** —
so its transaction discipline, its lint-as-gates, its counted open loops and its secret hygiene
were adopted, and the host that carries them (Claude Code, Obsidian, a marketplace install) was
refused, because charter §2 says the app may only ever be an optional lens.

## Adoption table

| claude-obsidian concept | What it actually is there | Verdict in HADES | Script / gate that holds it here | Test that proves it runs today |
|---|---|---|---|---|
| "Only one place ever writes to your vault — the transaction core" | skills and agents hand back drafts; one writer merges | **adopted as the plan door** — `hades.py plan` → `apply --approve` is the only structural write path, and an agent's own writes land on the quarantine shelf instead of the prose | `15_SYSTEM/scripts/hades.py`, `scripts/promote.py`, `15_SYSTEM/scripts/mcp_server.py` (`candidate_propose`) | `tests/test_phase21_records_are_visible.py`, `15_SYSTEM/scripts/test_hades.py` (`t_refusals`) |
| The transaction spec: one plan, one apply, a fingerprint per note, a conflict instead of an overwrite | the plan is checked against the bytes at apply time | **adopted, with the sharpest edge this repo has** — a plan carries `pre_image_sha1`; if the record moved since, `apply` refuses it as stale; a plan applies exactly once; `id`/`kind`/`created_at` are immutable; every accepted change appends `field, from, to, when, plan` to the record's own `amendments` trail | `15_SYSTEM/scripts/hades.py` (`pre_image_sha`, `cmd_apply_amend`, `cmd_apply_link`) | `tests/test_phase22_amend_a_record.py::test_an_amendment_planned_against_a_moved_record_is_refused_at_apply`, `tests/test_phase30_registry_hardening.py::test_a_plan_applies_once` |
| `transaction recover` + a journal: an interrupted write must not become a silent half-state | resumability of the write layer | **adopted twice** — the way back is bytes plus a fingerprint plus a journal (`fell_back: true`), and a partial write is *marked* rather than hidden (`.install-incomplete`, "existing source is incomplete") | `scripts/base.py`, `15_SYSTEM/scripts/backend/install_skill.py`, `15_SYSTEM/scripts/backend/sources.py` | `tests/test_phase20_known_good_base.py::test_a_journal_entry_whose_bytes_are_gone_is_refused_not_faked`, `tests/test_install_skill.py` |
| `wiki-lint`: dead links, orphan pages, gaps | a read-only agent that leaves a report | **adopted as gates, not as a report** — zero broken links is a build condition; the cycle's orphan, stale-inbox and unanswered-search signals become typed rows, and the gap register is exported as a tracked snapshot a clone can open | `scripts/link_check.py`, `scripts/frontmatter_check.py`, `scripts/loop.py`, `14_CANDIDATES/loop/gaps.jsonl` | `tests/test_toolchain.py::test_link_check_catches_broken_link`, `tests/test_phase19_evidence_survives_a_clone.py::test_the_kb_gap_signal_cites_a_snapshot_the_clone_can_read` |
| Open loops | things left unfinished, visible in a lint report | **adopted harder** — the shelf reconciles with its own ledger: `proposed == adopt + revise + drop + keep_base + open`, and a row that leaves the shelf without a disposition is reported as the lost measurement it is. An issue cannot be called fixed without a commit and a clone-readable evidence path | `scripts/candidate_check.py` (`ledger_problems`), `scripts/issues.py`, `15_SYSTEM/config/issues.json`, `14_CANDIDATES/loop/ledger.jsonl` | `tests/test_phase14_typed_candidates.py::test_a_row_that_vanishes_without_a_disposition_is_a_lost_measurement`, `::test_the_real_shelf_is_in_balance` |
| Secret hygiene and the privacy stance: no cloud database, no lock-in, no telemetry; remote models off until allowed; SECURITY/PRIVACY files | a policy plus a permission toggle | **adopted and pushed past it** — there is no socket to switch on. Secrets are refused at the write lint, scanned again by `doctor` (pattern **and** entropy), blocked a second time on any publish path, and refused by the default read boundary | `scripts/write_gate.py`, `15_SYSTEM/scripts/hades.py` (`scan_secrets`, the export block), `15_SYSTEM/scripts/backend/access.py`, `SECURITY.md` | `tests/test_phase3.py::test_secrets_blocked`, `15_SYSTEM/scripts/test_hades.py` (`m_secret_token`, `m_secret_labelled`, `m_secret_entropy`), `tests/test_access_boundary.py` |
| Fetched pages and transcripts are data, never instructions | prompt-injection hygiene | **adopted as the ingest law** — injection phrases and zero-width characters are blocked before content reaches Git, and CI proves the fence blocks on every run | `scripts/write_gate.py`, `AGENTS.md` ("untrusted data, not instructions") | `tests/test_phase3.py::test_injection_blocked`, `::test_zero_width_characters_blocked`, the write-gate smoke step in `.github/workflows/ci.yml` |
| Sources kept in `inbox/` as untouched, content-addressed originals; raw separate from extracted knowledge | capture first, wiki second | **adopted as the private source store** — the raw bytes are authoritative, the id is the sha256 of kind + origin + content (so a re-import is idempotent and changed content is a new record), and the index is disposable and rebuilt from the bytes | `15_SYSTEM/scripts/backend/sources.py`, `15_SYSTEM/scripts/sources.py` | `tests/test_sources.py`, `tests/test_batch.py` |
| "Every claim tied to its source" (Ground), with a provenance contract | provenance as a schema | **adopted as two refusals** — a dated claim without `source_url` + `observed_at` (+ `last_verified`) is warned as unverified, and a lesson without an exact quote inside an imported source is never written | `15_SYSTEM/schemas/manifest.schema.json`, `15_SYSTEM/scripts/backend/learning.py`, `scripts/memory.py`, `rules/memory.schema.json` | `tests/test_learning.py`, `tests/test_phase15_repo_memory.py`, `15_SYSTEM/scripts/test_hades.py` (`m_stale_date`) |
| Local BM25 search with optional reranking | retrieval over the vault, one shared index | **search adopted, rerank refused by default** — the BM25 index lives in one source for the door and the toolkit, `kb.py` indexes this brain's own prose, and embeddings sit behind `vector_search: false` where even perfect evidence still refuses until a production embedder is registered | `15_SYSTEM/scripts/backend/search.py`, `scripts/kb.py`, `scripts/vector.py`, `scripts/vector_check.py` | `tests/test_phase27_repo_corpus.py`, `tests/test_phase29_vector_seam.py`, `tests/test_retrieval_golden.py` |
| "Every session starts from your notes instead of from zero" | memory continuity across sessions | **adopted as a machine-fresh handoff plus a memory read before acting** — §1 of `HANDOFF.md` is generated and refused when its numbers drift, and `memory.py --recall` answers `NO_ENTRY` instead of inventing a lesson | `scripts/handoff.py`, `scripts/memory.py`, `MEMORY.md` | `tests/test_phase8.py::test_check_fresh_and_stale`, `tests/test_phase15_repo_memory.py` |
| Obsidian as the front end (Bases, Canvas, `.obsidian`, plugin marketplace install) | the app renders the vault | **refused (charter §2)** — markdown plus stdlib scripts *are* the system; an editor is an optional lens, and a shipped line that turns one into a requirement fails the build | `scripts/install.py`, `scripts/sync_hosts.py`, `pyproject.toml` | `tests/test_phase16_host_independence.py` |
| 15 skills + 3 agents distributed through a host's plugin mechanism | the deliverable is packaged for one harness | **logic adopted, packaging refused** — skills are `skills/*/SKILL.md` registered as records whose `entrypoint` `doctor` must be able to open; every host gets a *generated pointer* to one canon file instead of a second copy of the law | `skills/`, `15_SYSTEM/config/system.json` (`kinds`), `scripts/sync_hosts.py`, `15_SYSTEM/scripts/capabilities.py` | `tests/test_phase17_control_plane.py`, `tests/test_phase16_host_independence.py`, `tests/test_capabilities.py` |
| Methodology modes: Generic / LYT / PARA / Zettelkasten, switchable without moving files | one vault, many organisations on demand | **refused (charter §4, one standard structure)** — one placement rule per kind, enforced by the zone fence; a brain that re-organises itself by mood is exactly the scattered-files defect §3 warns against | `rules/zones.json`, `scripts/zone_check.py`, `15_SYSTEM/config/system.json` | `tests/test_phase3.py::test_zone_config_matches_skill_contract` |
| `init` / `adopt`: the tool decides where an existing note belongs | auto-organisation of a folder | **refused as an automatic act** — placement is a structural change: plan → review → `apply --approve`, and the installer never moves or overwrites a note (it refuses a non-empty target instead of touching it) | `15_SYSTEM/scripts/hades.py`, `scripts/install.py` | `tests/test_phase21_registry_enumeration_and_amendments.py`, `tests/test_phase6.py` |
| Transcript / session capture as a first-class source | the plugin records the conversation | **adopted as explicit selection only** — one named file at a time (CLI or the `source_import` tool), adapters for three *documented* stream formats, user/assistant text only, no folder scanning and no undocumented local history databases | `15_SYSTEM/scripts/sources.py`, `15_SYSTEM/scripts/backend/access.py`, `15_SYSTEM/integrations/local-sources.md` | `tests/test_sources.py`, `tests/test_access_boundary.py` |

## The transaction spec, translated

Upstream's spec and this repo's door want the same three things; the difference is who is held to
them (see `02_WIKI/decisions/WIK-B7ED0084-gates-enforce-laws-or-they-a.md` — a rule is only a rule
when a script refuses the opposite):

- **one plan, one apply** — `hades.py plan` writes a plan file and touches nothing; `apply --approve`
  is the only act that moves bytes. A second `apply` of the same plan does not amend twice.
- **a fingerprint on what is about to change** — `pre_image_sha1` on the plan; `apply` compares it
  with the file on disk and refuses a stale plan rather than overwriting work it never saw.
- **a journal, not a memory** — every accepted change appends to the record's own `amendments`
  ledger, the retirement verdict lives in `supersedes` (which takes the record out of the active
  index instead of deleting it), and the state-level journal is `14_CANDIDATES/loop/bases.jsonl`
  with `recovery.jsonl` beside it when a fall back actually happens.
- **conflict, never overwrite** — `promote.py` refuses to drop a promotion onto a destination
  inside `agent_edit_never` ("pick a new destination and let the human merge"), `source_sync.transfer`
  names conflicts and keeps both versions, and `install_skill.py` never replaces a directory.

## Secret hygiene is a gate, not a document

The upstream stance is a permission boundary ("remote off until you allow them"). Here it is a
refusal that fires in four places, all of them testable after a `git clone`:

1. `scripts/write_gate.py` — injection phrases, zero-width characters, `sk-`/`gh[pousr]_`/`xox`/`AKIA`
   patterns and card-shaped numbers, on text **and** on files, with exit 2 reserved for "I could not
   read it" so a refusal is never reported as clean.
2. `15_SYSTEM/scripts/hades.py` `scan_secrets` — pattern plus entropy across every zone `doctor`
   walks; the same scan blocks an `export` path before anything leaves.
3. `15_SYSTEM/scripts/backend/access.py` — the default read boundary refuses `.env`, key and
   credential filenames, `.git`, `secrets`, and the runtime / lab / candidate / backup zones.
4. `AGENTS.md` — no key, token, cookie or password in notes, logs, Git or prompts; store a
   `secret_ref` pointing at a secret manager instead.

## What was refused, in the charter's own terms

- **A host as the unit of distribution.** No marketplace install, no Claude-only skill tree, no
  Obsidian plugin: charter §2 forbids a mandatory dependency on any app, and §3's own instruction
  is to generalize the logic to *every* agent. The mechanism that replaced it is one canon file
  rendered to five doors (`scripts/sync_hosts.py`), with `--lint` refusing a door that points at a
  path that does not exist.
- **The app's data formats as the source of truth.** `.obsidian` state, Bases and Canvas files are
  lenses over markdown, so nothing in the gates reads them; the note contract is
  `rules/schema.json` and the record contract is `15_SYSTEM/config/system.json`.
- **Paid or hosted retrieval.** No cloud database, no embeddings service, no reranker that phones
  home — the seam exists (`backend/vector.py`) and stays inert (`scripts/vector_check.py`).
- **Machine-chosen placement.** Mode-switching and auto-`adopt` were refused: one structure, one
  placement per kind, and a human approving the plan.
- **Their limits, adopted as limits.** No PDF text extraction and no OCR: both need an external
  tool, so they stay refused rather than half-built; no web fetch in the gates at all — an ingested
  page is untrusted data, and a fetched page would need a runner this repo does not have.

## What the clone can open today

Measured 2026-11-02 in this checkout. `python scripts/health.py` runs nine gates and eight of them
print OK: the vault gates, the plane map, the shelf contract ("6 shelf candidate(s) meet the
contract; 6 proposed / 0 decided / 6 open"), memory ("27 lesson(s), 26 active"), the host doors,
the inert vector seam, and the issue ledger ("22 issue(s) on the ledger: 4 open, 1 partial, 4
fixed, 13 closed; every fixed row cites a commit and a clone-readable path"). The ninth,
`doc_report.py --check`, is red here and it is **not** this map's red: the measured blocks in
`README.md`, `HANDOFF.md` and `00_START_HERE/START.md` still quote 446 tests collected, 10 skills
and 15 registry records, while the tree measures more on all three rows (562 tests collected at the
moment this paragraph was written — the number moved twice while this map was being written, which
is exactly why the block is generated rather than typed). Another branch is landing tests, records
and a skill in this same working copy; the fix is `python scripts/doc_report.py --write`, owned by
whoever moved the count, and it rewrites files this map is not allowed to touch. Nothing here moves
a measured row: `doc_report.py` counts gates, records, skills, doors, lessons and shelf rows, and
writing a note changes none of them.

`14_CANDIDATES/loop/` holds six typed rows, all `proposed`; `15_SYSTEM/memory/lessons.jsonl` holds
27 rows with 26 active, one of them this reference's own lesson
(`mem-doors-must-point-at-real-rooms`); `02_WIKI/reference_maps/` holds one standing map per named
reference plus the plane map, and `02_WIKI/indexes/reference-maps.md` links them.

## Health law learned from this

Reachability, not decoration. claude-obsidian's `wiki-lint` only *reports* dead links and orphans;
here a dead link is a refusal: `scripts/link_check.py` is a gate in `scripts/health.py`, CI runs
that command, and `tests/test_phase16_host_independence.py` runs the installed brain's own
`health.py --vault .` — so a double-bracket link pointing at nothing fails a build on two machines
at once. That is also the shape this folder obeys: `scripts/install.py` ships `02_WIKI/reference_maps`
into every installed home but not `02_WIKI/indexes`, so these maps carry backticked paths only (a
wiki-link written here would dangle in every home that never received its target), and the one
place such links are safe is the index note at `02_WIKI/indexes/reference-maps.md`, which is never
shipped and links only tracked notes. The rest of the law is the same instinct as upstream's "every
claim tied to its source": a claim a reader cannot open is a claim that has not been made yet,
which is why every adopted row above names a script **and** a test. `doctor` refuses a registry
record whose `entrypoint` does not exist, and the lesson this map was found under says the same
thing about generated doors: a door naming a path that no longer exists republishes the dead link to
every agent at once — so the lint runs at render time and the render is refused.

## Final folder structure — answer

No new zone, no renumbering, nothing moved:

```
00_START_HERE/            CHARTER_AUDIT.md §3 now points at all three maps
01_INBOX … 10_ARCHIVE     the human plane; 02_WIKI gained this map and the reference index
11_CONTROL/               one placement per kind (modes and auto-adopt refused, not hidden)
14_CANDIDATES/loop/       the counted open loops: rows, ledger.jsonl, gaps.jsonl
15_SYSTEM/scripts/        hades.py (the transaction door), backend/sources.py, access.py, wiki.py
scripts/                  write_gate, link_check, frontmatter_check, candidate_check, sync_hosts
02_WIKI/reference_maps/   superagi · harness2 · this map · eight-memory-planes
02_WIKI/indexes/          reference-maps.md (one line per map; the only note holding wiki links)
```

`15_SYSTEM/scripts/wiki.py` is the one place a rendered site is built (human plane only, `noindex`,
bound to `127.0.0.1`), and `02_WIKI/_site/` it writes is generated output, not evidence.

## Still open, in order of value

Stated against `15_SYSTEM/config/issues.json` as it reads on 2026-11-02; each row is the tracker's
to close, not this map's.

1. **Contradiction detection** (#24, `open`) — upstream's `wiki-lint` reports gaps; nothing tracked
   compares two notes and names the disagreement. A measurable definition has to exist before the
   gate does, or the gate reports `errors: 0` over a pair it cannot see.
2. **The conversation path** (#20, `partial`) — import is explicit and proven (`sources.py`, the
   access boundary), but the walk from a session to durable knowledge is still carried by a person
   rather than by a tracked skill and a gate.
3. **Lessons typed by plane** (#25, `open`) — the memory this repo reads before acting is one
   undifferentiated ledger, so error memory and decision memory share a file and a reader cannot
   ask for just one kind.
4. **This issue's own row** — #22 is still `open` in the ledger even though the two maps now exist
   and are indexed: `scripts/issues.py --check` refuses `fixed` until a commit and a clone-readable
   evidence path back the claim. Documentation is not a merge.

## Where a fresh reader starts

`python scripts/health.py`, then `python -m unittest discover -s tests` with
`tests/test_phase3.py`, `tests/test_phase16_host_independence.py`,
`tests/test_phase22_amend_a_record.py` and `tests/test_phase14_typed_candidates.py`, then
`python scripts/issues.py --check` to see which loops the repo is still carrying. The sibling
maps in this folder are `02_WIKI/reference_maps/superagi-to-hades-map.md` and
`02_WIKI/reference_maps/harness2-to-hades-map.md`; the index is
`02_WIKI/indexes/reference-maps.md`; the law they all answer to is
`00_START_HERE/PROJECT_CHARTER.md` §2 and §3.
