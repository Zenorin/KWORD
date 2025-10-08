#!/usr/bin/env python3
# tools/verify_outputs.py
"""
Free Edition Output Verifier (D7)

Checks:
- required columns exist
- numeric columns coercible (no NaN)
- score in [0,100]
- duplicated keys: (seed, keyword) if both present, else (keyword)
- quick row counts for each artifact

Writes:
- output/_verify_report.md  (human-readable)
Exit codes:
- 0: OK
- 1: violations detected
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd

REQ_COLS = ["keyword","keyword_sanitized","comp_combined","intent_norm","competition_norm","score"]
NUM_COLS = ["comp_combined","intent_norm","competition_norm","score"]

def _read_csv(p: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeError:
        return pd.read_csv(p, encoding="utf-8")

def _key_cols(df: pd.DataFrame) -> Tuple[List[str], str]:
    if "seed" in df.columns and "keyword" in df.columns:
        return ["seed","keyword"], "seed+keyword"
    if "keyword" in df.columns:
        return ["keyword"], "keyword"
    return [], "NONE"

def verify(
    sanitized: Path, expanded: Path, competition: Path,
    scores_csv: Path, scores_xlsx: Optional[Path]=None, html: Optional[Path]=None
) -> Tuple[bool, List[str], str]:
    issues: List[str] = []

    # Load
    df = _read_csv(scores_csv)

    # 1) required columns
    missing = [c for c in REQ_COLS if c not in df.columns]
    if missing:
        issues.append(f"missing columns: {missing}")

    # 2) numeric coercion
    for col in NUM_COLS:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.isna().any():
                issues.append(f"NaN values in numeric column: {col}")
        else:
            issues.append(f"missing numeric column: {col}")

    # 3) score range
    if "score" in df.columns:
        s = pd.to_numeric(df["score"], errors="coerce")
        if (s.lt(0) | s.gt(100)).any():
            issues.append("score outside 0..100")

    # 4) duplicates
    keys, keyname = _key_cols(df)
    if not keys:
        issues.append("cannot determine key columns (need 'keyword' or 'seed'+'keyword')")
    else:
        dups = df.duplicated(subset=keys, keep=False)
        dup_cnt = int(dups.sum())
        if dup_cnt > 0:
            sample = df.loc[dups, keys + ["score"]].head(10)
            issues.append(f"duplicated keys by {keyname}: count={dup_cnt}\n{sample.to_string(index=False)}")

    # 5) artifacts headcounts
    def _safe_len(p: Path) -> str:
        try:
            return str(len(_read_csv(p)))
        except Exception:
            return "?"
    meta = [
        f"- sanitized:  {sanitized}  rows={_safe_len(sanitized)}",
        f"- expanded:   {expanded}   rows={_safe_len(expanded)}",
        f"- competition:{competition} rows={_safe_len(competition)}",
        f"- scores(csv):{scores_csv} rows={len(df)}",
    ]
    if scores_xlsx:
        meta.append(f"- scores(xlsx):{scores_xlsx}  exists={scores_xlsx.exists()}")
    if html:
        meta.append(f"- report(html): {html}  exists={html.exists()}")

    ok = len(issues) == 0

    # Write report
    out = Path("output/_verify_report.md")
    lines: List[str] = ["# Verify Report (D7)\n"]
    lines.append("## Artifacts")
    lines.extend(meta)
    lines.append("\n## Result")
    if ok:
        lines.append("- ✅ OK (no issues)")
    else:
        lines.append("- ❌ Issues found:")
        lines.extend([f"  - {x}" for x in issues])

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[{'OK' if ok else 'WARN'}] wrote: {out}")
    return ok, issues, str(out)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanitized", type=Path, default=Path("output/sanitized_keywords.csv"))
    ap.add_argument("--expanded", type=Path, default=Path("output/expanded_keywords.csv"))
    ap.add_argument("--competition", type=Path, default=Path("output/competition_counts.csv"))
    ap.add_argument("--scores-csv", type=Path, default=Path("output/keyword_scores_free.csv"))
    ap.add_argument("--scores-xlsx", type=Path, default=Path("output/keyword_scores_free.xlsx"))
    ap.add_argument("--html", type=Path, default=Path("output/report.html"))
    args = ap.parse_args()

    ok, _, _ = verify(args.sanitized, args.expanded, args.competition, args.scores_csv, args.scores_xlsx, args.html)
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
