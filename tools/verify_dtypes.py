#!/usr/bin/env python3
# tools/verify_dtypes.py
"""
C3: Simple dtype/column validator for Free Edition outputs.

- Checks that required columns exist with expected types/domains
- Ensures 'seed' is canonicalized to string-like (e.g., 1.0 -> "1")
- Emits a short markdown report: output/_dtype_report.md
- Exit 0 if OK, 1 if any violations
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import re

REQ_COLS = ["seed","keyword","keyword_sanitized","comp_combined","intent_norm","competition_norm","score"]

_float_like = re.compile(r"^\s*\d+(\.0+)?\s*$")
def _canon_seed_str(x: object) -> str:
    s = str(x).strip()
    m = _float_like.match(s)
    if m:
        try:
            f = float(s)
            if float(int(f)) == f:
                return str(int(f))
        except Exception:
            pass
    return s

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=Path("output/keyword_scores_free.csv"))
    args = ap.parse_args()

    p = args.scores
    if not p.exists():
        print(f"❌ missing file: {p}")
        return 1

    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeError:
        df = pd.read_csv(p, encoding="utf-8")

    issues: List[str] = []
    # 1) required columns
    missing = [c for c in REQ_COLS if c not in df.columns]
    if missing:
        issues.append(f"missing columns: {missing}")

    # 2) seed canonicalization check
    if "seed" in df.columns:
        bad = []
        for i, v in enumerate(df["seed"].astype(str)):
            if v and _float_like.match(v):  # looks like 1 or 1.0
                # we accept only plain integer string e.g. "1"
                if "." in v:
                    bad.append(i)
        if bad:
            issues.append(f"seed not canonicalized (has floats) count={len(bad)}")

    # 3) numeric columns coercible
    for col in ["comp_combined","intent_norm","competition_norm","score"]:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.isna().any():
                issues.append(f"NaN values in numeric column: {col}")

    # 4) score range
    if "score" in df.columns:
        s = pd.to_numeric(df["score"], errors="coerce")
        if (s.lt(0) | s.gt(100)).any():
            issues.append("score outside 0..100")

    # write report
    out = Path("output/_dtype_report.md")
    lines = ["# Dtype Verification Report\n", f"- file: {p}", f"- rows: {len(df)}\n"]
    if issues:
        lines.append("## Issues")
        lines.extend([f"- {x}" for x in issues])
        out.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        print(f"\n[WARN] wrote: {out}")
        return 1
    else:
        lines.append("## Result\n- ✅ OK (no issues)")
        out.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        print(f"\n[OK] wrote: {out}")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
