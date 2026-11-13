#!/usr/bin/env python3
"""Measure a reproducible *local* first recall with only synthetic Markdown.

This is an offline smoke/latency probe for the existing keyword KB CLI, not a
semantic-memory benchmark or a git-clone timer. Every trial uses a new temporary
brain; no user files, network services, LLMs, or repositories are written.

Usage: python scripts/first_success.py --repeat 3
Returns JSON and exits nonzero if any synthetic ingest/recall trial fails.
"""
import argparse
import datetime
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = "02_WIKI/demo.md"
QUERY = "ORCHIDMEMORY2026"
MAX_REPEAT = 10


def trial(kb_script, timeout=30):
    """Run both CLI commands with synthetic data and an isolated SQLite cache."""
    with tempfile.TemporaryDirectory(prefix="sbo-first-recall-") as tmp:
        vault = Path(tmp)
        notes = vault / "02_WIKI"
        notes.mkdir()
        (notes / "demo.md").write_text(
            "# Example memory\n" + QUERY + " is a made-up recall marker.\n",
            encoding="utf-8")
        (notes / "distractor.md").write_text(
            "# A different note\nThis note has no matching token.\n",
            encoding="utf-8")

        def invoke(*args):
            return subprocess.run(
                [sys.executable, str(kb_script), *args, "--vault", str(vault)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout, check=False)

        start = time.perf_counter()
        try:
            ingest = invoke("ingest")
            if ingest.returncode != 0:
                return {"success": False, "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                        "reason": "ingest_exit_nonzero"}
            search = invoke("search", QUERY)
            elapsed = round((time.perf_counter() - start) * 1000, 3)
        except subprocess.TimeoutExpired:
            return {"success": False, "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                    "reason": "timeout"}
        except OSError:
            return {"success": False, "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                    "reason": "process_start_failed"}

        index = (vault / ".kb" / "kb.sqlite").is_file()
        # Only the matching note can appear as a result; the search must not
        # silently return an unrelated note, or only an empty/error message.
        paths = re.findall(r"(?m)^((?:[\w-]+/)+[\w.-]+\.md)\s+\[", search.stdout)
        indexed = re.search(r"\bindexed (\d+) notes\b", ingest.stdout)
        passed = (search.returncode == 0 and index and indexed is not None
                  and int(indexed.group(1)) == 2 and paths == [EXPECTED])
        return {"success": bool(passed), "elapsed_ms": elapsed,
                "reason": "ok" if passed else "unexpected_search_or_index",
                "indexed_notes": int(indexed.group(1)) if indexed else None,
                "matched_paths": paths}


def evaluate(repeat, kb_script):
    samples = [trial(kb_script) for _ in range(repeat)]
    successes = sum(1 for sample in samples if sample["success"])
    durations = [sample["elapsed_ms"] for sample in samples]
    return {
        "schema_version": 1,
        "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "probe": "synthetic_keyword_ingest_then_recall",
        "scope": "local CLI subprocess startup + synthetic indexing + keyword search; excludes clone, health and setup",
        "dependencies": "Python standard library; no model or account",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "repeat": repeat,
        "successes": successes,
        "success_rate": round(successes / repeat, 3),
        "median_ms": round(statistics.median(durations), 3),
        "max_ms": max(durations),
        "status": "pass" if successes == repeat else "fail",
        "trials": samples,
    }


def main(argv=None, kb_script=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3,
                        help="number of independent synthetic trials (1..10, default 3)")
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= MAX_REPEAT:
        parser.error("--repeat must be between 1 and %d" % MAX_REPEAT)
    script = Path(kb_script) if kb_script is not None else HERE / "kb.py"
    result = evaluate(args.repeat, script)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
