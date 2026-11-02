# Optional local Laya decision engine

Source: https://github.com/NandhaKishorM/laya (Apache-2.0). This is an *adapter*,
not a vendored copy of Laya or its weights. Python >=3.10 is needed for Laya;
Second Brain OS itself remains compatible with Python >=3.9. The adapter does
not activate by default, and never downloads models during normal startup, health
checks, or CI unit tests.

## Windows installation (Python 3.11)

From the Second Brain OS repository root:

```powershell
py -3.11 -m venv .venv-laya
.\.venv-laya\Scripts\python.exe -m pip install -r requirements-laya.txt
$env:SBO_LAYA_ENABLED = "1"
.\.venv-laya\Scripts\python.exe scripts/orchestrator.py tool list
.\.venv-laya\Scripts\python.exe scripts/orchestrator.py tool call --tool core.laya_decide --args '{"state":"یادداشت دیروز را پیدا کن","questions":{"route":{"type":"choice","instructions":"Which subsystem should handle this request?","criteria":{"memory":"Find or recall previous notes","human":"Ask a person for a decision","workflow":"Run a preapproved workflow"}}}}}'
```

Python 3.10+ on Linux/macOS: create a dedicated virtual environment with
`python3 -m venv .venv-laya`, then run `.venv-laya/bin/python -m pip install -r requirements-laya.txt`.
Set `SBO_LAYA_ENABLED=1` in the process environment before using the Laya tool.

**Model download:** Laya's `Router()` downloads its selected Hugging Face
checkpoint on its first real prediction. No weights are committed here. Use
the normal Laya/PyTorch setup instructions for GPU selection and offline caching.
The Laya process needs sufficient RAM/VRAM; using a separate Python environment
avoids changing the standard-library-only core installation.

**Privacy:** state and questions are sent to the locally loaded model, not
to a remote inference endpoint by this adapter. An initial network download
may still occur. Do not route private information until checkpoint sources
and cache locations have been reviewed. No input/output is persisted by this
adapter. Caller-controlled logs and external plugins require separate review.

## Contract and limits

- `core.laya_decide` is a **read-only** tool in the same orchestrator toolkit;
  any existing `tool_call` workflow can reference it. It returns JSON text.
- Types: `choice` (2-20 named options), `score` (2-20 ordered labels) and
  `noul` (probability of yes).
- Each output includes `status: proposed|review_required`, per-answer
  confidence and `actions_executed: false`. No choice is directly executable.
- The default 0.85 confidence threshold is a conservative **placeholder**, not
  a calibrated safety or accuracy guarantee. Low/missing confidence and out-of-set
  answers always require review. Calibrate per use case before relying on proposals.
- Run `python -m unittest tests.test_laya_adapter -v` without Laya installed to
  verify validation and fail-closed behavior. These are mock-based integration
  tests, **not** a real inference benchmark.
- The current integration does **not** automatically route every incoming MCP
  request, persist memories, fine-tune models or act without human approval.
  A future policy-gated routing layer may consume its output after an independent
  benchmark and explicit owner approval.

Check installation with this interpreter:

```powershell
.\.venv-laya\Scripts\python.exe -c "import laya; print('Laya import OK')"
```

If Laya is not installed, unavailable, or disabled, only Laya-backed calls are
refused; existing search, memory, toolkit and MCP behaviors keep working.
