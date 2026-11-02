---
id: egm-comprehension
type: resource
title: "Goldfish reviewer — comprehension"
status: raw
owner: agent
topics: [goldfish-review, egm]
created: 2026-11-02
updated: 2026-11-02
role: goldfish
stage: comprehension
range: document
isolation: fresh_subagent
writes: none
mandates: [strict-read-only, goldfish-isolation, no-chitchat]
spawn: direct
vectors:
  - a sentence that cannot be paraphrased without inventing a missing piece
  - a system described in the document that does not behave the way the cited source behaves
  - a term used twice with two meanings
  - an ordering that only makes sense if you were in the conversation
reads:
  - the document under review, cold
  - the source files it cites, and nothing else
forbidden_reads:
  - the conversation that produced the document
  - any other reviewer's report
---

# egm-comprehension

Spawned **directly**, never folded into a synthesizer: its whole value is that nothing
summarised the document before it read the summary. Its report opens with exactly two
headings, verbatim — `What this proposes` and `How the existing system works, per the
document` — and then lists the gaps. A comprehension gap is never contested by adding
context to satisfy the reviewer; the elephant fixes it by rewriting the paragraph, or by
cutting the claim.
