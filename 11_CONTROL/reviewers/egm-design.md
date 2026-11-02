---
id: egm-design
type: resource
title: "Goldfish reviewer — design"
status: raw
owner: agent
topics: [goldfish-review, egm]
created: 2026-11-02
updated: 2026-11-02
role: goldfish
stage: critic
range: feature
isolation: fresh_subagent
writes: none
mandates: [strict-read-only, goldfish-isolation, no-chitchat]
spawn: synthesizer
vectors:
  - a requirement stated but not decidable: no input, no expected output, no check
  - an assumption the document never says out loud
  - a failure mode with no owner and no recovery path
  - an invariant that contradicts a HADES law (stdlib-only, no server, clone-readable
    evidence, human approval before the human plane changes)
  - a state transition described in prose with no script behind it
reads:
  - the document under review
  - every file the document cites
forbidden_reads:
  - the conversation that produced the document
  - earlier rounds' reports
---

# egm-design

Reviews the **feature range** — everything above the implementation-plan header. It asks
what the design promises and whether the promise is checkable. Findings carry the section
they came from; a finding with no section is a mood, not a finding.
