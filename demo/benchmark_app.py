"""
Agent vs LUT benchmark dashboard. Run from repo root:

    pip install -e ".[demo]"
    python demo/benchmark_app.py

Open http://127.0.0.1:5050
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Repo root = parent of demo/
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from flask import Flask, Response, render_template, request, stream_with_context

from agent_lut.indexer import iter_python_files

_HERE = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(_HERE / "templates"))

# Rough GPT-4o-class pricing for demo display only (USD per 1M tokens).
_PRICE_IN_PER_M = 2.50
_PRICE_OUT_PER_M = 10.00


def _default_map_path() -> Path:
    return (_ROOT / "map.json").resolve()


def _estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in / 1_000_000.0) * _PRICE_IN_PER_M + (tokens_out / 1_000_000.0) * _PRICE_OUT_PER_M


def compute_map_footprint(*, repo_root: Path, map_path: Path) -> dict:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    py_files = iter_python_files(repo_root, respect_gitignore=True)
    codebase_tokens = 0
    for p in py_files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        codebase_tokens += len(enc.encode(text))

    map_tokens = 0
    if map_path.is_file():
        map_text = map_path.read_text(encoding="utf-8", errors="replace")
        map_tokens = len(enc.encode(map_text))

    pct = (100.0 * map_tokens / codebase_tokens) if codebase_tokens else 0.0
    return {
        "repo_root": str(repo_root),
        "map_path": str(map_path),
        "py_file_count": len(py_files),
        "codebase_tokens": codebase_tokens,
        "map_tokens": map_tokens,
        "map_pct_of_codebase": round(pct, 2),
    }


def _naive_metrics(*, depth: int, latency_s: float) -> dict:
    tokens_in = 200 + 1000 + (depth * 2000)
    tokens_out = 500
    return {
        "label": "naive",
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "latency_s": round(latency_s, 2),
        "steps": depth + 1,
        "estimated_cost_usd": round(_estimate_cost_usd(tokens_in, tokens_out), 4),
    }


def _lut_metrics(*, latency_s: float) -> dict:
    tokens_in = 300 + 2000
    tokens_out = 150
    return {
        "label": "lut",
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "latency_s": round(latency_s, 2),
        "steps": 2,
        "estimated_cost_usd": round(_estimate_cost_usd(tokens_in, tokens_out), 4),
    }


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def run_benchmark_events(*, depth: int, map_stats: dict | None):
    """Yield SSE payload dicts: log lines, phase updates, final complete."""
    yield {"type": "log", "line": "Starting head-to-head benchmark (simulated agent paths).", "phase": None}

    # --- Naive path ---
    yield {"type": "phase", "phase": "naive", "status": "running"}
    t0 = time.perf_counter()

    yield {"type": "log", "line": "[Naive] Read project README (~200 tok context).", "phase": "naive"}
    time.sleep(0.55)
    yield {"type": "log", "line": "[Naive] Opened wrong module A (~1000 tok).", "phase": "naive"}
    time.sleep(0.55)

    for i in range(depth):
        yield {
            "type": "log",
            "line": f"[Naive] Grepped / opened file {i + 1}/{depth} (~2000 tok each).",
            "phase": "naive",
        }
        time.sleep(0.45)

    yield {"type": "log", "line": "[Naive] Found target file.", "phase": "naive"}
    naive_latency = time.perf_counter() - t0
    naive = _naive_metrics(depth=depth, latency_s=naive_latency)
    yield {"type": "phase", "phase": "naive", "status": "done", "metrics": naive}

    # --- LUT path ---
    yield {"type": "phase", "phase": "lut", "status": "running"}
    t1 = time.perf_counter()

    yield {"type": "log", "line": "[LUT] Consulted keyword map (~300 tok).", "phase": "lut"}
    time.sleep(0.4)
    yield {"type": "log", "line": "[LUT] Read single target file (~2000 tok).", "phase": "lut"}
    time.sleep(0.4)

    lut_latency = time.perf_counter() - t1
    lut = _lut_metrics(latency_s=lut_latency)
    yield {"type": "phase", "phase": "lut", "status": "done", "metrics": lut}

    n_tok = naive["tokens_total"]
    l_tok = lut["tokens_total"]
    token_savings_pct = ((n_tok - l_tok) / n_tok * 100) if n_tok else 0.0
    speed_boost = (naive["latency_s"] / lut["latency_s"]) if lut["latency_s"] else 0.0

    yield {
        "type": "complete",
        "naive": naive,
        "lut": lut,
        "delta": {
            "token_savings_pct": round(token_savings_pct, 1),
            "speed_boost": round(speed_boost, 1),
            "steps_naive": naive["steps"],
            "steps_lut": lut["steps"],
        },
        "map_stats": map_stats,
    }


@app.get("/")
def index():
    return render_template("benchmark.html")


@app.get("/api/map-stats")
def api_map_stats():
    repo_root = Path(request.args.get("repo", str(_ROOT))).resolve()
    map_path = Path(request.args.get("map", str(_default_map_path()))).resolve()
    return compute_map_footprint(repo_root=repo_root, map_path=map_path)


@app.get("/api/benchmark/stream")
def api_benchmark_stream():
    depth = request.args.get("depth", default=5, type=int)
    depth = max(1, min(depth, 20))
    include_map = request.args.get("map", default="1") not in ("0", "false", "no")

    map_stats: dict | None = None
    if include_map:
        try:
            map_stats = compute_map_footprint(repo_root=_ROOT, map_path=_default_map_path())
        except Exception as e:  # noqa: BLE001 — demo resilience
            map_stats = {"error": str(e)}

    def generate():
        for evt in run_benchmark_events(depth=depth, map_stats=map_stats):
            yield _sse(evt)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)


if __name__ == "__main__":
    main()
