#!/usr/bin/env python3
# tools/make_report_plus.py
"""
C4: Lightweight dashboard HTML for Free Edition.

- Reads output/keyword_scores_free.csv
- Produces output/report_plus.html
- Includes:
  - Top N by score
  - Top N per seed (if seed column exists)
  - Visual bars using simple CSS (no extra deps)
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import html

def _bar(pct: float, label: str) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    return f'''
    <div style="background:#eee;border-radius:6px;height:14px;position:relative;">
      <div style="background:#36c;width:{pct:.2f}%;height:14px;border-radius:6px"></div>
      <div style="position:absolute;left:6px;top:-2px;font:12px/14px system-ui;color:#111">{html.escape(label)}</div>
    </div>'''

def _table(df: pd.DataFrame, title: str, topn: int = 10) -> str:
    cols = [c for c in ["seed","keyword","score","competition_norm","intent_norm","comp_combined"] if c in df.columns]
    d = df.copy().sort_values("score", ascending=False).head(topn)
    rows = []
    for _, r in d.iterrows():
        seed = html.escape(str(r.get("seed","")))
        kw = html.escape(str(r.get("keyword","")))
        score = float(r.get("score", 0))
        compn = float(r.get("competition_norm", 0))
        intentn = float(r.get("intent_norm", 0))
        bar = _bar(score, f"{score:.1f}")
        rows.append(f"<tr><td>{seed}</td><td>{kw}</td><td style='min-width:160px'>{bar}</td><td>{intentn:.2f}</td><td>{compn:.2f}</td></tr>")
    head = "<tr><th>seed</th><th>keyword</th><th>score</th><th>intent_norm</th><th>competition_norm</th></tr>"
    return f"<h3>{html.escape(title)}</h3><table>{head}{''.join(rows)}</table>"

def _per_seed(df: pd.DataFrame, per: int = 5) -> str:
    if "seed" not in df.columns:
        return ""
    html_blocks = ["<h2>Top by seed</h2>"]
    for seed, g in df.groupby("seed"):
        if str(seed).strip()=="":
            continue
        html_blocks.append(_table(g, f"Seed: {seed}", topn=per))
    return "\n".join(html_blocks)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=Path("output/keyword_scores_free.csv"))
    ap.add_argument("--out", type=Path, default=Path("output/report_plus.html"))
    ap.add_argument("--topn", type=int, default=10)
    ap.add_argument("--per-seed", type=int, default=5)
    args = ap.parse_args()

    df = pd.read_csv(args.scores, encoding="utf-8-sig")
    css = """
    <style>
      body{font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif;margin:20px}
      table{border-collapse:collapse;width:100%;margin:10px 0 24px}
      th,td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px}
      th{background:#f8fafc;text-align:left}
      h1,h2,h3{margin:16px 0 8px}
      .muted{color:#6b7280;font-size:12px}
    </style>
    """
    top_html = _table(df, "Top by score", topn=args.topn)
    seed_html = _per_seed(df, per=args.per_seed)

    html_out = f"""
    <html><head><meta charset="utf-8"><title>Keyword Score Dashboard</title>{css}</head>
    <body>
      <h1>Keyword Score Dashboard</h1>
      <div class="muted">Generated from {html.escape(str(args.scores))}</div>
      {top_html}
      {seed_html}
    </body></html>
    """
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_out, encoding="utf-8")
    print("[OK] Wrote:", args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
