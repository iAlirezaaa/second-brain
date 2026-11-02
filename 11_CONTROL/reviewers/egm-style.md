---
id: egm-style
type: resource
title: "Goldfish reviewer — style"
status: raw
owner: agent
topics: [goldfish-review, egm]
created: 2026-11-02
updated: 2026-11-02
role: goldfish
stage: [critic, implementation_readiness]
range: [feature, implementation]
isolation: fresh_subagent
writes: none
mandates: [strict-read-only, goldfish-isolation, no-chitchat]
spawn: synthesizer
vectors:
  - a doc-surface cost: a paragraph every host must now keep in sync for one clause of law
  - the same rule stated twice in two files, so the next edit changes one of them
  - a term invented where the repo already has a word for it
  - a claim written as a certainty with no command behind it
  - prose that explains a procedure instead of stating it
reads:
  - the range it is dispatched over
  - the file that already owns the rule it is reading
forbidden_reads:
  - the conversation that produced the document
---

# egm-style

Runs over both ranges: `critic` on the feature range, `implementation_readiness` on the plan.
Style here is not taste — in a repo whose documents are read by six harnesses before they act,
a redundant paragraph is a maintenance cost and a contradiction waiting to happen. Its findings
are Nits by default; only a duplicate law that can disagree with itself gets raised to Major.
