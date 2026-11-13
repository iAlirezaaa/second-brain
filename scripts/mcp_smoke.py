#!/usr/bin/env python3
"""Prove the local MCP stdio door on throwaway notes, without host configuration.

This is a protocol smoke check, not an external-host compatibility certification or
an OS access-control test. No private brain data is loaded or transmitted.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "15_SYSTEM" / "scripts" / "mcp_server.py"
NOTE_PATH = "02_WIKI/mcp-smoke-note.md"
SENTINEL = "sbo_smoke_coral_7843"
PROTOCOL_VERSION = "2025-06-18"


def _exchange(server, root, messages, strict, timeout):
    """Run a bounded stdio conversation; never run against a person's home."""
    env = os.environ.copy()
    # These child processes see ONLY root's synthetic note. Explicitly test the
    # legacy read path and the opt-in strict session boundary in separate runs.
    env["SBO_REQUIRE_SESSION"] = "1" if strict else "0"
    env["PYTHONIOENCODING"] = "utf-8"
    payload = "".join(json.dumps(message, ensure_ascii=True) + "\n" for message in messages)
    process = subprocess.run([sys.executable, str(server), "--root", str(root)],
                             input=payload, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", cwd=str(root),
                             env=env, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError("MCP server exited %s: %s" %
                           (process.returncode, process.stderr[-300:].strip()))
    responses = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    indexed = {message.get("id"): message for message in responses}
    expected = {message["id"] for message in messages if "id" in message}
    if len(indexed) != len(responses) or set(indexed) != expected:
        raise RuntimeError("MCP response ids do not match requests")
    return indexed


def _result(responses, message_id):
    row = responses[message_id]
    if row.get("jsonrpc") != "2.0" or "error" in row or not isinstance(row.get("result"), dict):
        raise RuntimeError("MCP JSON-RPC response failed at id %s" % message_id)
    return row["result"]


def run_probe(server=SERVER, timeout=20):
    """Return evidence or raise; two subprocesses, one disposable synthetic brain."""
    server = Path(server)
    if server.is_symlink() or not server.is_file():
        raise FileNotFoundError("MCP server must be an existing regular file")
    if not 1 <= timeout <= 60:
        raise ValueError("timeout must be 1..60 seconds")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="sbo-mcp-smoke-") as temporary:
        root = Path(temporary)
        note = root / NOTE_PATH
        note.parent.mkdir(parents=True)
        note.write_text("# MCP smoke fixture\nSynthetic only: %s\n" % SENTINEL,
                        encoding="utf-8")
        initial = _exchange(server, root, [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {}, "clientInfo": {"name": "sbo-smoke", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "vault_search", "arguments": {"query": SENTINEL}}},
        ], strict=False, timeout=timeout)
        hello = _result(initial, 1)
        if hello.get("protocolVersion") != PROTOCOL_VERSION:
            raise RuntimeError("unexpected MCP protocol version")
        tools = _result(initial, 2).get("tools", [])
        tags = {row.get("name"): row.get("behavior") for row in tools}
        if tags.get("vault_search") != "read_only" or tags.get("candidate_propose") != "idempotent":
            raise RuntimeError("missing/mis-tagged MCP tools")
        search = _result(initial, 3)
        text = "\n".join(str(item.get("text", "")) for item in search.get("content", []))
        if search.get("isError") or NOTE_PATH not in text or SENTINEL not in text:
            raise RuntimeError("MCP search did not cite the synthetic source")
        guarded = _exchange(server, root, [
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "candidate_propose",
                        "arguments": {"cue": "synthetic cue", "lesson": "synthetic lesson"}}},
        ], strict=True, timeout=timeout)
        rejection = _result(guarded, 4)
        reason = "\n".join(str(item.get("text", "")) for item in rejection.get("content", []))
        if not rejection.get("isError") or "strict agent session mode requires" not in reason:
            raise RuntimeError("strict-mode write was not explicitly refused")
        if (root / "14_CANDIDATES").exists():
            raise RuntimeError("strict-mode write created a candidate shelf")
    return {"status": "ok", "synthetic": True, "transport": "stdio-newline-jsonrpc",
            "protocol": PROTOCOL_VERSION, "tools_listed": len(tools),
            "source_path": NOTE_PATH, "strict_write_refused": True,
            "no_candidate_written": True,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=20,
                        help="per-process timeout in seconds (1..60; default 20)")
    args = parser.parse_args(argv)
    try:
        report = run_probe(timeout=args.timeout)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
