# Security Policy — second-brain

## Supported versions

| Version | Supported |
|---------|-----------|
| latest `main` / latest tag | ✅ |
| older tags | ❌ (upgrade — the whole project is stdlib, upgrades are cheap) |

## Reporting a vulnerability

Use **GitHub's private vulnerability reporting** on this repository
(Security → Advisories → New draft security advisory). Do **not** open a public issue.

## What is (and is not) in scope

In scope:
- the write gate (`scripts/write_gate.py`) failing to block injections / zero-width characters / leaked secrets
- `run_health` / loop / handoff scripts leaking or destroying vault data
- the installer (`scripts/install.py`) writing outside its target or copying credential files

Out of scope:
- anything in `12_RUNTIME/`, `13_LAB/` or `.kb/` (machine-plane scratch, gitignored by design)
- the HADES plane scripts (`15_SYSTEM/`) maintained by the owner for personal use

## Expectations

This is a small, stdlib-only project. Best-effort response within **7 days**;
fix shipped as a patch release in the next tag.
