---
name: health
description: Composite vault check — link integrity + frontmatter validity. Run at the end of every agent session.
---

# health

One command, always at session end:

```
python scripts/health.py
```

Green (exit 0) means: zero broken links, every note carries valid frontmatter.
Red means stop and fix before proposing anything else. Prevention beats
correction — the same principle as tests in code.
