#!/usr/bin/env python3
# tools/make_report_plus.py
"""
Report+ (Free Edition): searchable/sortable HTML dashboard.

- Input : output/keyword_scores_free.csv
- Output: output/report_plus.html
- Features:
  * Top N by score
  * Top N per seed
  * Keyword/Seed 검색 필터
  * 헤더 클릭 정렬 (score 등)
  * 현재 보이는 테이블 CSV로 내보내기(클라이언트 사이드)

No external deps beyond pandas.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import html

def _bar(pct: float, label: str) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    return (
        "<div style='background:#eee;border-radius:6px;height:14px;position:relative;'>"
        f"<div style='background:#36c;width:{pct:.2f}%;height:14px;border-radius:6px'></div>"
        f"<div style='position:absolute;left:6px;top:-2px;font:12px/14px system-ui;color:#111'>{html.escape(label)}</div>"
        "</div>"
    )

def _table_rows(df: pd.DataFrame) -> str:
    rows = []
    for _, r in df.iterrows():
        seed = html.escape(str(r.get("seed", "")))
        kw = html.escape(str(r.get("keyword", "")))
        score = float(r.get("score", 0))
        compn = float(r.get("competition_norm", 0))
        intentn = float(r.get("intent_norm", 0))
        bar = _bar(score, f"{score:.1f}")
        # data-attrs for client-side filter/sort
        rows.append(
            "<tr>"
            f"<td data-seed='{seed}'>{seed}</td>"
            f"<td data-kw='{kw}'>{kw}</td>"
            f"<td data-score='{score:.6f}' style='min-width:160px'>{bar}</td>"
            f"<td data-intent='{intentn:.6f}'>{intentn:.2f}</td>"
            f"<td data-comp='{compn:.6f}'>{compn:.2f}</td>"
            "</tr>"
        )
    return "".join(rows)

def _table(df: pd.DataFrame, title: str, topn: int) -> str:
    use = df.copy().sort_values("score", ascending=False).head(topn)
    head = (
        "<tr>"
        "<th data-col='seed'>seed</th>"
        "<th data-col='keyword'>keyword</th>"
        "<th data-col='score'>score</th>"
        "<th data-col='intent_norm'>intent_norm</th>"
        "<th data-col='competition_norm'>competition_norm</th>"
        "</tr>"
    )
    return f"<h3>{html.escape(title)}</h3><table class='rpt'>{head}{_table_rows(use)}</table>"

def _per_seed(df: pd.DataFrame, per: int) -> str:
    if "seed" not in df.columns:
        return ""
    blocks = ["<h2>Top by seed</h2>"]
    for seed, g in df.groupby("seed"):
        if str(seed).strip() == "":
            continue
        blocks.append(_table(g, f"Seed: {seed}", topn=per))
    return "\n".join(blocks)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=Path("output/keyword_scores_free.csv"))
    ap.add_argument("--out", type=Path, default=Path("output/report_plus.html"))
    ap.add_argument("--topn", type=int, default=20)
    ap.add_argument("--per-seed", type=int, default=5)
    args = ap.parse_args()

    df = pd.read_csv(args.scores, encoding="utf-8-sig")

    # base CSS/JS (search + sort + export)
    css = """
    <style>
      *{box-sizing:border-box}
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:20px;color:#0f172a}
      h1,h2,h3{margin:14px 0 8px}
      .muted{color:#6b7280;font-size:12px}
      .toolbar{display:flex;gap:12px;align-items:center;margin:10px 0 14px}
      input[type="search"]{padding:8px 10px;border:1px solid #e5e7eb;border-radius:8px;min-width:280px}
      button{padding:8px 12px;border:1px solid #e5e7eb;background:#fff;border-radius:8px;cursor:pointer}
      button:hover{background:#f8fafc}
      table.rpt{border-collapse:collapse;width:100%;margin:10px 0 24px}
      th,td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px;text-align:left;vertical-align:top}
      th{background:#f8fafc;cursor:pointer;user-select:none}
      .pin{background:#eef2ff}
      .hint{font-size:12px;color:#64748b}
    </style>
    """
    js = """
    <script>
    (function(){
      function toCSV(table){
        const rows=[...table.querySelectorAll('tr')];
        return rows.map(r=>[...r.children].map(td=>{
          const t=td.innerText.replaceAll('"','""');
          return `"${t}"`;
        }).join(",")).join("\\n");
      }
      function downloadCSV(table, name){
        const blob=new Blob([toCSV(table)],{type:"text/csv;charset=utf-8"});
        const a=document.createElement("a");
        a.href=URL.createObjectURL(blob);
        a.download=name||"table.csv";
        a.click();
        URL.revokeObjectURL(a.href);
      }
      function applyFilter(root, q){
        const kw=q.toLowerCase();
        root.querySelectorAll("table.rpt").forEach(tbl=>{
          const trs=[...tbl.querySelectorAll("tbody tr")];
          trs.forEach(tr=>{
            const s=(tr.querySelector("td[data-seed]")?.dataset.seed||"").toLowerCase();
            const k=(tr.querySelector("td[data-kw]")?.dataset.kw||"").toLowerCase();
            tr.style.display = (s.includes(kw)||k.includes(kw)) ? "" : "none";
          });
        });
      }
      function attachSort(tbl){
        const getVal=(td,col)=>parseFloat(td.dataset[col])||td.innerText.toLowerCase();
        tbl.querySelectorAll("th").forEach(th=>{
          th.addEventListener("click",()=>{
            const col = th.dataset.col;
            if(!col) return;
            const tbody = tbl.tBodies[0];
            const rows = [...tbody.rows];
            const asc = !(th.classList.contains("pin"));
            rows.sort((a,b)=>{
              const va = getVal(a.cells[th.cellIndex], col);
              const vb = getVal(b.cells[th.cellIndex], col);
              if(typeof va==="number" && typeof vb==="number") return asc ? va-vb : vb-va;
              return asc ? (""+va).localeCompare(""+vb) : (""+vb).localeCompare(""+va);
            });
            tbody.append(...rows);
            tbl.querySelectorAll("th").forEach(x=>x.classList.remove("pin"));
            th.classList.add("pin");
          });
        });
      }
      function boot(){
        const root=document;
        const q=root.getElementById("q");
        const expButtons=[...root.querySelectorAll("[data-export]")];
        const tables=[...root.querySelectorAll("table.rpt")];
        tables.forEach(attachSort);
        if(q){ q.addEventListener("input", e=>applyFilter(root, e.target.value)); }
        expButtons.forEach(btn=>{
          btn.addEventListener("click",()=>{
            const i=parseInt(btn.dataset.export,10);
            const tbl=tables[i];
            if(tbl) downloadCSV(tbl, (btn.dataset.name||"table")+".csv");
          });
        });
      }
      document.addEventListener("DOMContentLoaded", boot);
    })();
    </script>
    """

    # Build sections
    top_html = _table(df, "Top by score", topn=args.topn)
    seed_html = _per_seed(df, per=args.per_seed)

    html_out = f"""
    <html><head><meta charset="utf-8"><title>Keyword Score Dashboard+</title>{css}</head>
    <body>
      <h1>Keyword Score Dashboard+</h1>
      <div class="muted">Generated from {html.escape(str(args.scores))}</div>
      <div class="toolbar">
        <input id="q" type="search" placeholder="Filter by keyword or seed…" />
        <button data-export="0" data-name="top_by_score">Export visible (Top)</button>
        <span class="hint">Tip: 헤더를 클릭하면 정렬됩니다.</span>
      </div>
      {top_html}
      {seed_html}
      {js}
    </body></html>
    """
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_out, encoding="utf-8")
    print("[OK] Wrote:", args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
