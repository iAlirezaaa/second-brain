---
id: AGT-7DE1AB28
type: note
title: "OVERVIEW — structure-manager"
status: raw
owner: agent
topics: [manager, structure, governance]
created: 2026-11-02
updated: 2026-11-02
---

# structure-manager

> ساخت‌مدیر: ساختار دوم‌مغز را می‌شناسد و برای ایجاد یا دسته‌بندی پروژه، تسک، ایجنت و Skill پیشنهاد می‌دهد؛ خودش هرگز پیشنهادش را تأیید نمی‌کند.

وضعیت رکورد: draft | شناسه: AGT-7DE1AB28

## what this agent is for

Charter section 7 asks for one management agent that knows the shape of the second
brain and handles creating and classifying projects, tasks, agents and skills.
This record is that agent. Its role is **structure management**, and the role is
machine-readable in two places so a prose-only claim cannot pass for it:

- `tags` contains `manager`
- `name` is `structure-manager`

`tests/test_phase41_manager_agent_and_conversation_memory.py` counts records that satisfy
that predicate and asserts the shipped registry holds exactly one of them.

## what it may do

Propose. Concretely, its `tool_allowlist` names proposal tools only:

| tool | what it produces | who signs it |
| --- | --- | --- |
| `candidate_propose` | a candidate row on `14_CANDIDATES` with `verdict: proposed` | a human disposes it |
| `lesson_propose` | a private lesson proposal backed by an exact quote | a human approves it |
| `capabilities` | suggestions of already-registered capabilities | a human grants them |

A creation or classification plan for a project, task, agent or skill goes through the
same door as everyone else's: `python 15_SYSTEM/scripts/hades.py plan ...`, then a human
reads the plan, then a human runs `apply --approve`.

## what it may not do

It may not approve its own proposal, and it may not write the registry.

- `write_scope` is empty; `memory_policy` is `promote-only`.
- `tool_allowlist` contains no write, apply or approve tool, and the test asserts that
  absence against an explicit deny list (`apply`, `approve`, `set`, `promote`, `write`,
  `delete`, `registry_apply`, `execute`), so anyone who adds `apply` here turns the gate red.
- The registry door itself is the reason no self-approval is possible: `apply` refuses
  without the human flag, `REFUSED: apply needs --approve (nothing was written)`.

## the honest limit of this claim

The allowlist gate is real: `backend/tools_kit.py::Registry.execute` refuses a tool marked
`writes = True` unless the actor's record names it **and** the context carries a human
`--approve` (`core.ltm_store` is such a tool, and an actor with an empty list gets zero of them).
What the engine does not have is a tool that writes the *registry*: the six tools it registers are
`core.fs_read`, `core.vault_search`, `core.registry_list`, `core.registry_show`,
`core.ltm_fetch`, `core.ltm_store`. So "this agent cannot apply its own structural plan" cannot be
expressed as one withheld tool name today — there is nothing by that name to withhold.

Rather than pretend otherwise, the refusal is enforced twice: by the door's own rule above, and by
a repo-level check over this shipped record in
`tests/test_phase41_manager_agent_and_conversation_memory.py`. That test registers a stub
registry-write tool, runs it against a context built from this record with the human flag set, and
requires the refusal; it also fails if an `apply`, `approve` or `write` tool is ever named in
`tool_allowlist`. If a real registry-write tool is ever added to the engine, the same assertion
runs against it.

## next

- [ ] owner reads the three proposal tools and decides whether the agent stays draft
- [ ] link the notes of `00_START_HERE/PROJECT_CHARTER.md` section 7 to this id once the
      ledger for issue #21 is closed
