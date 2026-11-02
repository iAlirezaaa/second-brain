---
id: egm-codebase-details
type: resource
title: "Goldfish reviewer — codebase details"
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
  - a file, script, function or config key the plan names that does not exist
  - a plan that needs a third-party package, a network call, a port or a daemon
  - Python newer than the 3.9 floor the repo tests on
  - a step that writes into the human plane without the `--approve` door
  - evidence that only exists on the author's laptop (behind the documented git boundary)
reads:
  - the implementation range of the document
  - every source file that range touches
forbidden_reads:
  - the conversation that produced the document
---

# egm-codebase-details

Opens every path the plan names and answers one question: is it there? A citation that does
not resolve is a Blocker, because the plan is about to be executed by a stranger who cannot
ask. This reviewer is the reason the repo's claims survive a `git clone`.
