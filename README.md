# second-brain · نسخه / v0.0.3

An AI-augmented second brain: a plain-markdown vault that a human curates and AI agents maintain.

- **Plain markdown you own** — Obsidian-compatible (`[[wikilinks]]`, frontmatter). No database, no lock-in.
- **Fenced zones** — the agent writes freely only in its zones; your notes (`20_Notes`) need approval.
- **Integrity toolchain** — zero broken links, validated frontmatter, vault stats. Every rule is a script, not a suggestion.
- **Skills, not prompts** — each workflow is a written protocol an agent can follow deterministically.

See [ROADMAP.md](ROADMAP.md) for the build plan and status.

## Quickstart

```bash
git clone https://github.com/iAlirezaaa/second-brain.git
cd second-brain
python -m unittest discover -s tests -v   # everything green = vault is healthy
```

Open `vault-template/` as an Obsidian vault, and point your agent (Claude Code / OpenCode) at the repo — it reads `AGENTS.md` first.

## The two audiences

| You (human) | Your agent |
|---|---|
| Reads `index.md`, browses the map | Reads `AGENTS.md` + `rules/zones.json` on session start |
| Curates `20_Notes`, makes judgment calls | Triages `00_Inbox`, proposes placements with a one-line why |
| Writes rules, audits diffs in git | Writes freely in `90_Agent_Output`, never edits `20_Notes` |

## License

MIT

---

## نسخهٔ فارسی

یک سکند برین مبتنی بر هوش مصنوعی: والتی از فایل‌های مارک‌داون ساده که انسان آن را سرپرستی می‌کند و ایجنت‌ها نگه‌داری‌اش می‌کنند.

- **مارک‌داون ساده، مالکیت کامل** — سازگار با Obsidian (`لینک‌های [[]]` و فرانت‌متر). بدون دیتابیس، بدون وابستگی به ابزار خاص.
- **زون‌های حصارکشی‌شده** — ایجنت فقط در زون خودش آزادانه می‌نویسد؛ نوت‌های شما (`20_Notes`) بدون تأیید شما دست‌نخورده می‌مانند.
- **ابزارهای سلامت** — صفر لینک شکسته، فرانت‌متر معتبر، آمار ولت. هر قاعده یک اسکریپت است، نه یک جملهٔ توصیه‌ای.
- **Skill نه prompt** — هر گردش کار یک پروتکل مکتوب است که ایجنت به‌صورت قطعی اجرا می‌کند.

نقشهٔ راه و وضعیت: [ROADMAP.md](ROADMAP.md).

### شروع سریع

```bash
git clone https://github.com/iAlirezaaa/second-brain.git
cd second-brain
python -m unittest discover -s tests -v   # سبز = ولت سالم است
```

پوشهٔ `vault-template/` را به‌عنوان Vault در Obsidian باز کنید و ایجنت (Claude Code / OpenCode) را به همین ریپو نشانه بروید — او اول `AGENTS.md` را می‌خواند.

### دو مخاطب

| شما (انسان) | ایجنت شما |
|---|---|
| `index.md` را می‌خواند، نقشه را مرور می‌کند | شروع هر سشن اول `AGENTS.md` + `rules/zones.json` را می‌خواند |
| نوت‌های خودش را کیوریت می‌کند، قضاوت با اوست | صندوق ورودی (`00_Inbox`) را تریاژ می‌کند و «کجا بجای این نوت + دلیل در یک خط» پیشنهاد می‌دهد |
| قوانین را می‌نویسد، دیف‌های git را بازبینی می‌کند | در `90_Agent_Output` آزاد است و هرگز `20_Notes` را ویرایش نمی‌کند |

### مجوز

MIT
