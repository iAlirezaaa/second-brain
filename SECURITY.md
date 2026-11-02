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

## Cryptographic primitives

`15_SYSTEM/scripts/backend/crypto.py` implements ChaCha20-Poly1305 (RFC 8439) with a scrypt/PBKDF2
key-derivation layer and a versioned container format, in pure Python.

Read this before you rely on it:

- **Self-authored, not third-party-audited.** No external review has been done, and no bug bounty
  claim is made for it. The standard library has no AEAD construction, and the project keeps
  stdlib as its default, so the engine was written here rather than imported.
- **Its credibility is a test, not a sentence.** `python 15_SYSTEM/scripts/backend/crypto.py
  --selftest` re-checks the RFC's known-answer vectors and every tamper case on every machine, and
  `tests/test_phase51_chacha20_poly1305.py` runs in the suite that CI executes on each push. A
  change that breaks a known-answer vector fails the build — the gate is what holds the claim up.
- **A container is one version, with no negotiation.** The header must state a kdf id and parameters
  this build can run; if it cannot, it says so and stops instead of falling back to something
  weaker. The versioned format is what lets an audited engine replace this one later without
  rewriting the bytes on disk.
- **A seal command exists; the restore proof does not cross machines yet.** `scripts/vault.py` seals
  and opens the planes the `private_planes` of `15_SYSTEM/config/system.json` names, and
  `scripts/vault_check.py` refuses to let `encrypted_private_backup` be on without a witness judged by
  its shape. So "encryption at rest" is now a surface someone can call — on the machine that holds
  the key — while §8's *regular restore test*, on a machine that never saw the bytes, is still open.
  See `ROADMAP.md`, Phase 52, for exactly what is missing.

## Expectations

This is a small, stdlib-only project. Best-effort response within **7 days**;
fix shipped as a patch release in the next tag.
