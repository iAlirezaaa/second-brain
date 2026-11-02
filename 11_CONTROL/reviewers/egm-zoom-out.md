---
id: egm-zoom-out
type: resource
title: "Goldfish reviewer — zoom out"
status: raw
owner: agent
topics: [goldfish-review, egm]
created: 2026-11-02
updated: 2026-11-02
role: goldfish
stage: [zoom_out, intermediate_zoom_out]
range: [feature, implementation, document]
isolation: fresh_subagent
writes: none
mandates: [strict-read-only, goldfish-isolation, no-chitchat]
spawn: synthesizer
vectors:
  - the problem the document solves is not the problem the repo has
  - one feature presented as three, or three compressed into one unreviewable blob
  - non-goals absent, so scope has no edge to measure against
  - a decision taken silently where the doc should have said "we chose A over B"
  - the fixes added since the last pass widening the document again
reads:
  - the document under review, top to bottom
  - every file the document cites
forbidden_reads:
  - the conversation that produced the document
  - earlier rounds' reports and the elephant's reasoning
---

# egm-zoom-out

Runs first (`zoom_out`) and again after the fixes land (`intermediate_zoom_out`): the second
pass audits only what the applied fixes *added*, because a fix is a new piece of a document
nobody has read cold. Report scope, missing non-goals and silent decisions; never re-litigate
a settled finding. Its report is a file the clone can open —
`90_Agent_Output/reviews/<FEATURE>/rounds/egm-zoom-out-<round>.md` — and the roster row names it.
