#!/usr/bin/env python3
# tools/make_golden_snapshot.py
"""
Create a deterministic "golden" snapshot from regression outputs.

- Copies regression CSVs to output/golden/regression/
- Writes manifest.json with sha256, row/col counts (KST timestamp)
- Targeted files: sanitized, expanded, competition, scores

Usage:
  python -u tools/make_golden_snapshot.py \
    --base-dir output/regression \
    --out-dir output/golden/regression
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

import pandas as pd

KST = timezone(timedelta(hours=9))

FILES = [
    "sanitized_keywords.csv",
    "expanded_keywords.csv",
    "competition_counts.csv",
    "keyword_scores_free.csv",
]

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def _peek(p: Path) -> Dict[str, Any]:
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeError:
        df = pd.read_csv(p, encoding="utf-8")
    return {"rows": int(len(df)), "cols": int(len(df.columns))}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, default=Path("output/regression"))
    ap.add_argument("--out-dir", type=Path, default=Path("output/golden/regression"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "created_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "base_dir": str(args.base_dir),
        "files": {},
    }

    for name in FILES:
        src = args.base_dir / name
        dst = args.out_dir / name
        if not src.exists():
            raise SystemExit(f"ERROR: missing source {src}")
        dst.write_bytes(src.read_bytes())
        meta = _peek(dst)
        meta["sha256"] = _sha256(dst)
        manifest["files"][name] = meta

    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("[OK] Golden snapshot written to:", args.out_dir)
    for n, m in manifest["files"].items():
        print(f" - {n}: rows={m['rows']}, cols={m['cols']}, sha256={m['sha256'][:12]}…")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
