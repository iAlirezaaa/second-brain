---
id: egm-implementation-readiness
type: resource
title: "Goldfish reviewer — implementation readiness"
status: raw
owner: agent
topics: [goldfish-review, egm]
created: 2026-11-02
updated: 2026-11-02
role: goldfish
stage: implementation_readiness
range: implementation
isolation: fresh_subagent
writes: none
mandates: [strict-read-only, goldfish-isolation, no-chitchat]
spawn: synthesizer
vectors:
  - a step a stranger cannot execute: no command, no file, no expected output
  - no test named for a change that is claimed to be provable
  - steps ordered so that a later one is a precondition of an earlier one
  - a step that needs the human's approval but never says where the door is
  - an acceptance check that cannot be read off the finished artifact
reads:
  - the implementation range only, split at the implementation-plan header
  - the tests and scripts that range edits
forbidden_reads:
  - the conversation that produced the document
---

# egm-implementation-readiness

Reviews the **implementation range** — everything from the implementation-plan header down.
It reads as if it were handed the plan and nothing else, then tries to execute it in its own
head step by step. Every finding must say which step broke and what the step would have had
to contain instead.
