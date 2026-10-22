"""Measure peak RSS of loading all-MiniLM-L6-v2 via PyTorch vs FastEmbed (ONNX).

Each measurement runs in a fresh subprocess so imports, caches and the
allocator start clean. The child embeds the same batch, then reports its own
peak resident set size (Windows: peak working set; Linux/macOS: ru_maxrss).

Usage (the two variants need different environments):

    python scripts/bench_memory.py \\
        --python-onnx .venv/Scripts/python \\
        --python-torch path/to/python-with-sentence-transformers \\
        --runs 5

or a single variant for debugging:

    python scripts/bench_memory.py --child onnx

Scope: this measures the *embedding stage in isolation* (import + model load +
one batch), not the whole FastAPI process on Render.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
BATCH = [f"Metformin is the first-line drug for type 2 diabetes, claim number {i}." for i in range(64)]


def _peak_rss_bytes() -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()  # type: ignore[attr-defined]
        ctypes.windll.psapi.GetProcessMemoryInfo(  # type: ignore[attr-defined]
            ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb
        )
        return int(counters.PeakWorkingSetSize)
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _child(variant: str) -> None:
    import time

    t0 = time.perf_counter()
    if variant == "torch":
        import sentence_transformers
        import torch
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(MODEL, device="cpu")
        vecs = model.encode(BATCH)
        versions = {"torch": torch.__version__, "sentence-transformers": sentence_transformers.__version__}
    elif variant == "onnx":
        import fastembed
        import onnxruntime
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=MODEL)
        vecs = list(model.embed(BATCH))
        versions = {"fastembed": getattr(fastembed, "__version__", "?"), "onnxruntime": onnxruntime.__version__}
    else:
        raise SystemExit(f"unknown variant {variant}")
    print(
        json.dumps(
            {
                "variant": variant,
                "peak_rss_mb": _peak_rss_bytes() / 1024 / 1024,
                "dim": len(vecs[0]),
                "seconds": time.perf_counter() - t0,
                "versions": versions,
            }
        )
    )


def _run(python: str, variant: str) -> dict:
    out = subprocess.run(
        [python, __file__, "--child", variant], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--child", choices=["torch", "onnx"], help="internal: run one measurement in this process")
    ap.add_argument("--python-torch", default=sys.executable)
    ap.add_argument("--python-onnx", default=sys.executable)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--json-out", help="write raw results here")
    args = ap.parse_args()

    if args.child:
        _child(args.child)
        return 0

    # One warm-up per variant so the model files are already downloaded and cached.
    results: dict[str, list[dict]] = {}
    for variant, py in (("torch", args.python_torch), ("onnx", args.python_onnx)):
        _run(py, variant)
        results[variant] = [_run(py, variant) for _ in range(args.runs)]

    med = {v: statistics.median(r["peak_rss_mb"] for r in rs) for v, rs in results.items()}
    reduction = (1 - med["onnx"] / med["torch"]) * 100
    print(f"Platform: {platform.platform()}  Python: {platform.python_version()}  runs: {args.runs}")
    for v, rs in results.items():
        vals = [r["peak_rss_mb"] for r in rs]
        print(f"{v:6s} median {med[v]:7.1f} MB  min {min(vals):7.1f}  max {max(vals):7.1f}  {rs[0]['versions']}")
    print(f"Peak-RSS reduction (torch -> onnx): {reduction:.1f}%")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"platform": platform.platform(), "results": results, "reduction_pct": reduction}, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
