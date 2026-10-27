---
id: "WIK-B7ED0084"
kind: "wiki_note"
name: "Gates enforce laws or they are comments"
status: "draft"
classification: "internal"
created_at: "2026-10-27"
last_verified: "2026-10-27"
source_url: "https://github.com/iAlirezaaa/second-brain/issues/12"
topic: "decision"
tags: []
notes: "A rule written in a config, a README or a schema is only a rule when a script refuses the opposite. Three were found in one pass of this repo's own self-audit: supersedes was declared as leaving the active index while index listed both records and doctor printed errors: 0; enumeration matched one filename (note.md) while target_path wrote <ID>-<slug>.md, so a record could be created and then answer NOT FOUND; and the registry was create-only, which made duplicating a definition the only way to correct it. Each was fixed test-first: the phase 21/22/23 tests are red without their feature, and each fix states the law in AGENTS.md so every host projection carries it. The decision worth recording is the order: measure the wrong behaviour in a fresh replica first, write the test that reproduces it, then make the gate bite -- never trust a local green as proof. A fourth defect was caught by using the feature the moment it shipped: amending a markdown record rewrote its body from fields the reader could not see, and deleted the paragraph; prose now lives in a field that round-trips."
relations: {}
amendments: [{"field": "source_url", "from": null, "to": "https://github.com/iAlirezaaa/second-brain/issues/12", "utc": "2026-10-27T19:28:21Z", "plan": "PLAN-496694DC1D5A"}, {"field": "last_verified", "from": null, "to": "2026-10-27", "utc": "2026-10-27T19:28:21Z", "plan": "PLAN-4C5AB42D7195"}, {"field": "notes", "from": null, "to": "A rule written in a config, a README or a schema is only a rule when a script refuses the opposite. Three were found in one pass of this repo's own self-audit: supersedes was declared as leaving the active index while index listed both records and doctor printed errors: 0; enumeration matched one filename (note.md) while target_path wrote <ID>-<slug>.md, so a record could be created and then answer NOT FOUND; and the registry was create-only, which made duplicating a definition the only way to correct it. Each was fixed test-first: the phase 21/22/23 tests are red without their feature, and each fix states the law in AGENTS.md so every host projection carries it. The decision worth recording is the order: measure the wrong behaviour in a fresh replica first, write the test that reproduces it, then make the gate bite -- never trust a local green as proof. A fourth defect was caught by using the feature the moment it shipped: amending a markdown record rewrote its body from fields the reader could not see, and deleted the paragraph; prose now lives in a field that round-trips.", "utc": "2026-10-27T19:32:26Z", "plan": "PLAN-B182EEC46244"}]
---

# Gates enforce laws or they are comments

A rule written in a config, a README or a schema is only a rule when a script refuses the opposite. Three were found in one pass of this repo's own self-audit: supersedes was declared as leaving the active index while index listed both records and doctor printed errors: 0; enumeration matched one filename (note.md) while target_path wrote <ID>-<slug>.md, so a record could be created and then answer NOT FOUND; and the registry was create-only, which made duplicating a definition the only way to correct it. Each was fixed test-first: the phase 21/22/23 tests are red without their feature, and each fix states the law in AGENTS.md so every host projection carries it. The decision worth recording is the order: measure the wrong behaviour in a fresh replica first, write the test that reproduces it, then make the gate bite -- never trust a local green as proof. A fourth defect was caught by using the feature the moment it shipped: amending a markdown record rewrote its body from fields the reader could not see, and deleted the paragraph; prose now lives in a field that round-trips.

## منبع

https://github.com/iAlirezaaa/second-brain/issues/12

## وضعیت

`draft` | مشاهده در `` | آخرین بررسی: `2026-10-27`
