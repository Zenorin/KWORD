#!/usr/bin/env python3
# tools/compute_scores.py
"""
Compute final keyword scores by merging:
- sanitized/expanded keywords
- competition counts (Coupang/Naver)
- Excel config (weights, intent tokens)

Outputs:
- CSV: output/keyword_scores_free.csv (UTF-8-SIG)
- XLSX: output/keyword_scores_free.xlsx (with filters & basic styling)
- (optional) HTML: output/report.html (Top-N table)
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd


# ---------- Helpers (column detection) ----------

def _detect_col(cols: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    cl = [c.lower() for c in cols]
    for cand in candidates:
        if cand.lower() in cl:
            return cols[cl.index(cand.lower())]
    return None


def _detect_col_fuzzy(cols: Sequence[str], substrings: Sequence[str]) -> Optional[str]:
    for name in cols:
        low = name.lower()
        if any(sub in low for sub in substrings):
            return name
    return None


def _guess_seed_col(df: pd.DataFrame) -> Optional[str]:
    cols = list(df.columns)
    col = _detect_col(cols, ["seed", "seed_index", "root", "parent", "group", "source_seed", "seed_name"])
    if col:
        return col
    return _detect_col_fuzzy(cols, ["seed", "parent", "root", "group"])


def _guess_keyword_col(df: pd.DataFrame) -> Optional[str]:
    cols = list(df.columns)
    # Strong candidates
    strong = [
        "keyword", "keyword_sanitized",
        "related_keyword", "expanded_keyword",
        "expanded", "expansion",
        "suggest", "suggestion",
        "candidate", "variant",
        "term", "query", "kw", "text", "title",
        "source",  # reported case
        # Korean aliases
        "확장키워드", "확장_키워드", "추천어", "연관키워드",
    ]
    col = _detect_col(cols, strong)
    if col:
        return col
    # Fuzzy substrings
    col = _detect_col_fuzzy(cols, ["keyword", "query", "term", "title", "suggest", "expand", "연관", "추천", "확장", "source"])
    if col:
        return col
    # Heuristic
    blacklist = {"seed", "seed_index", "category", "cat", "idx", "id", "index", "group", "count", "rank"}
    best_col, best_score = None, -1.0
    sample = df.head(50)
    for name in cols:
        if name.lower() in blacklist:
            continue
        values = sample[name].astype(str).fillna("").tolist()
        non_empty = [v for v in values if v.strip()]
        if not non_empty:
            continue
        avg_len = sum(len(v) for v in non_empty) / max(1, len(non_empty))
        uniq = len(set(non_empty))
        fill = len(non_empty) / max(1, len(values))
        score = avg_len * (0.5 + 0.5 * fill) + 0.05 * uniq
        if score > best_score:
            best_score = score
            best_col = name
    return best_col


def _minmax(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    min_v = s.min()
    max_v = s.max()
    rng = max_v - min_v
    if pd.isna(min_v) or pd.isna(max_v) or rng == 0:
        return pd.Series([0.0] * len(s), index=s.index, dtype=float)
    return (s - min_v) / rng


# ---------- Robust Excel config reader ----------

def _coerce_num(x) -> Optional[float]:
    try:
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except Exception:
        return None


def _truthy(x) -> bool:
    s = str(x).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def _read_excel_config(xlsx: Path) -> Tuple[float, float, List[Tuple[str, float]]]:
    """
    Returns:
      W_intent, W_competition (renormalized),
      tokens: list of (token, weight) for enabled==True (fallback to all if no 'enabled' col)
    """
    cfg = pd.read_excel(xlsx, sheet_name="config", engine="openpyxl")
    cfg_cols = list(cfg.columns)

    # ---- Weights detection ----
    w_int: Optional[float] = None
    w_cmp: Optional[float] = None

    # 1) Column-based
    col_wi = _detect_col(cfg_cols, ["w_intent"])
    col_wc = _detect_col(cfg_cols, ["w_competition"])
    if col_wi and col_wc:
        wi_series = pd.to_numeric(cfg[col_wi], errors="coerce")
        wc_series = pd.to_numeric(cfg[col_wc], errors="coerce")
        w_int = next((v for v in wi_series if pd.notna(v)), None)
        w_cmp = next((v for v in wc_series if pd.notna(v)), None)

    # 2) Key/Value table
    if w_int is None or w_cmp is None:
        kv_key = _detect_col(cfg_cols, ["key", "name", "metric", "k"])
        kv_val = _detect_col(cfg_cols, ["value", "val", "num", "v"])
        if kv_key and kv_val:
            for _, row in cfg[[kv_key, kv_val]].dropna(subset=[kv_key]).iterrows():
                k = str(row[kv_key]).strip().lower()
                v = _coerce_num(row[kv_val])
                if v is None:
                    continue
                if k == "w_intent":
                    w_int = v
                elif k == "w_competition":
                    w_cmp = v

    # 3) Literal scan
    if w_int is None or w_cmp is None:
        for r in range(len(cfg)):
            for c in range(len(cfg_cols)):
                val = str(cfg.iloc[r, c]).strip().lower()
                if val in {"w_intent", "w_competition"}:
                    # right neighbor
                    if c + 1 < len(cfg_cols):
                        v = _coerce_num(cfg.iloc[r, c + 1])
                        if v is not None:
                            if val == "w_intent" and w_int is None:
                                w_int = v
                            elif val == "w_competition" and w_cmp is None:
                                w_cmp = v
                            continue
                    # below neighbor
                    if r + 1 < len(cfg):
                        v = _coerce_num(cfg.iloc[r + 1, c])
                        if v is not None:
                            if val == "w_intent" and w_int is None:
                                w_int = v
                            elif val == "w_competition" and w_cmp is None:
                                w_cmp = v

    # Defaults & renormalize
    if w_int is None or w_cmp is None:
        w_int, w_cmp = 0.55, 0.45
    s = (w_int or 0) + (w_cmp or 0)
    if s <= 0:
        w_int, w_cmp = 0.55, 0.45
    else:
        w_int, w_cmp = float(w_int) / s, float(w_cmp) / s

    # ---- Tokens detection ----
    tok_col = _detect_col(cfg_cols, ["token", "tokens", "intent_token"])
    w_col = _detect_col(cfg_cols, ["weight", "w", "score"])
    en_col = _detect_col(cfg_cols, ["enabled", "enable", "active"])

    tokens: List[Tuple[str, float]] = []
    if tok_col and w_col:
        df_tok = cfg[[tok_col, w_col] + ([en_col] if en_col else [])].copy()
        df_tok = df_tok.dropna(subset=[tok_col, w_col])
        if en_col:
            df_tok = df_tok[df_tok[en_col].map(_truthy)]
        df_tok[w_col] = pd.to_numeric(df_tok[w_col], errors="coerce")
        df_tok = df_tok.dropna(subset=[w_col])
        for t, w in df_tok[[tok_col, w_col]].itertuples(index=False):
            t = str(t).strip()
            if not t:
                continue
            tokens.append((t, float(w)))

    return w_int, w_cmp, tokens


# ---------- Intent proxy ----------

def _compute_intent_proxy(text: str, tokens: List[Tuple[str, float]]) -> float:
    if not text or not tokens:
        return 0.0
    t = str(text).lower()
    s = 0.0
    for token, w in tokens:
        if str(token).lower() in t:
            s += float(w)
    return s


# ---------- Load base with fallback ----------

def _load_base(expanded_in: Optional[Path], sanitized_in: Optional[Path]) -> Tuple[pd.DataFrame, Path, str, Optional[str]]:
    """
    Returns: (base_df, src_used, keyword_col, seed_col or None)
    Tries expanded first, then sanitized; applies robust keyword/seed detection.
    """
    tried_info: List[Tuple[Path, List[str]]] = []
    for src in (expanded_in, sanitized_in):
        if src and src.exists():
            df = pd.read_csv(src, encoding="utf-8-sig")
            kw_col = _guess_keyword_col(df)
            if kw_col:
                seed_col = _guess_seed_col(df)
                return df, src, kw_col, seed_col
            tried_info.append((src, list(df.columns)))
    lines = ["ERROR: Could not detect a keyword column in base CSVs.", "Tried sources:"]
    for src, cols in tried_info:
        lines.append(f" - {src}: columns={cols}")
    raise SystemExit("\n".join(lines))


# ---------- Canonicalization ----------

_float_like = re.compile(r"^\s*\d+(\.0+)?\s*$")

def _canon_seed_str(x: object) -> str:
    """
    Normalize seed values so that 1.0 -> '1', keep strings as-is (trimmed).
    """
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


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop exact duplicates by (seed, keyword) if available, else by keyword.
    Keep the first occurrence to preserve order/score determinism.
    """
    keys = [c for c in ["seed", "keyword"] if c in df.columns]
    if not keys:
        return df
    return df.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)


# ---------- Pipeline ----------

def compute_scores(
    excel_in: Path,
    sanitized_in: Optional[Path],
    expanded_in: Optional[Path],
    competition_in: Optional[Path],
    out_csv: Path,
    out_xlsx: Optional[Path],
    html_out: Optional[Path],
    topn: int,
) -> None:
    print("[INFO] Reading Excel config:", excel_in)
    w_int, w_cmp, tokens = _read_excel_config(excel_in)
    print(f"[OK] Weights: W_intent={w_int:.4f}, W_competition={w_cmp:.4f}")
    print(f"[OK] Tokens: {len(tokens)} loaded")

    # Load base with fallback (expanded → sanitized)
    base_df, src_used, kw_col, seed_col = _load_base(expanded_in, sanitized_in)
    print(f"[INFO] Loaded base rows: {len(base_df)} from {src_used}")
    print(f"[INFO] Detected columns → keyword: '{kw_col}' | seed: '{seed_col or 'None'}'")

    # -------- Build base (copy; no rename collisions) --------
    base = pd.DataFrame()
    if seed_col and seed_col in base_df.columns:
        base["seed"] = base_df[seed_col].map(_canon_seed_str)
    else:
        base["seed"] = ""
    base["keyword"] = base_df[kw_col].astype(str)

    if "keyword_sanitized" in base_df.columns:
        ks = base_df["keyword_sanitized"].astype(str)
        fill_src = base_df[kw_col].astype(str)
        mask = ks.isna() | ks.str.strip().eq("")
        ks = ks.where(~mask, fill_src)
        base["keyword_sanitized"] = ks
    else:
        base["keyword_sanitized"] = base["keyword"]

    # -------- Load competition (optional, very robust) --------
    comp = None
    if competition_in and competition_in.exists():
        comp = pd.read_csv(competition_in, encoding="utf-8-sig")
        # Drop unnamed indexy columns
        comp = comp.loc[:, [c for c in comp.columns if not str(c).lower().startswith("unnamed")]]

        # Try to detect columns
        comp_seed = _detect_col(comp.columns, ["seed", "seed_index", "parent", "root", "seed_name"])
        comp_kw = _detect_col(comp.columns, [
            "keyword", "term", "query",
            "expanded_keyword", "expansion", "expanded",
            "child", "variant", "kw", "text", "title", "source",
            "연관키워드", "추천어", "확장키워드", "확장_키워드",
        ]) or _detect_col_fuzzy(comp.columns, ["keyword", "query", "term", "title", "expand", "source", "연관", "추천", "확장"])

        c_coup = _detect_col(comp.columns, ["comp_coupang", "coupang", "comp_cp"])
        c_nav = _detect_col(comp.columns, ["comp_naver", "naver", "comp_nv"])
        c_comb = _detect_col(comp.columns, ["comp_combined", "combined", "score_comp"])

        # If keyword col still unknown, try heuristic pick
        if not comp_kw:
            comp_kw = _guess_keyword_col(comp)

        # Normalize column names where found
        cols_map: Dict[str, str] = {}
        if comp_seed:
            cols_map[comp_seed] = "seed"
        if comp_kw:
            cols_map[comp_kw] = "keyword"
        if c_coup:
            cols_map[c_coup] = "comp_coupang"
        if c_nav:
            cols_map[c_nav] = "comp_naver"
        if c_comb:
            cols_map[c_comb] = "comp_combined"
        if cols_map:
            comp = comp.rename(columns=cols_map)

        if "keyword" not in comp.columns:
            print("[WARN] competition file has no recognizable keyword column; skipping merge.")
            comp = None
        else:
            # ---- Canonicalize dtypes before merge ----
            comp["keyword"] = comp["keyword"].astype(str)
            if "seed" in comp.columns:
                comp["seed"] = comp["seed"].map(_canon_seed_str)

            # derive combined if missing
            if "comp_combined" not in comp.columns or comp["comp_combined"].isna().all():
                cc = pd.to_numeric(comp.get("comp_coupang", pd.Series([None] * len(comp))), errors="coerce").fillna(0)
                nn = pd.to_numeric(comp.get("comp_naver", pd.Series([None] * len(comp))), errors="coerce").fillna(0)
                comp["comp_combined"] = (cc.add(1).apply(math.log) + nn.add(1).apply(math.log))

            # select only existing target columns
            select_cols = [c for c in ["seed", "keyword", "comp_coupang", "comp_naver", "comp_combined"] if c in comp.columns]
            comp = comp[select_cols]

    # -------- Merge base + competition --------
    if comp is not None and "seed" in comp.columns and "seed" in base.columns:
        merged = pd.merge(base, comp, on=["seed", "keyword"], how="left")
    elif comp is not None:
        merged = pd.merge(base, comp.drop(columns=[c for c in ["seed"] if c in comp.columns]), on=["keyword"], how="left")
    else:
        merged = base.copy()

    # ---- Fill NaNs for competition metrics to avoid NaN scores ----
    if "comp_coupang" in merged.columns:
        merged["comp_coupang"] = pd.to_numeric(merged["comp_coupang"], errors="coerce").fillna(0.0)
    if "comp_naver" in merged.columns:
        merged["comp_naver"] = pd.to_numeric(merged["comp_naver"], errors="coerce").fillna(0.0)
    if "comp_combined" in merged.columns:
        merged["comp_combined"] = pd.to_numeric(merged["comp_combined"], errors="coerce").fillna(0.0)
    else:
        merged["comp_combined"] = 0.0

    # -------- Intent proxy & normalizations --------
    print("[INFO] Computing intent proxies...")
    merged["intent_proxy"] = merged["keyword_sanitized"].astype(str).apply(lambda x: _compute_intent_proxy(x, tokens))

    merged["intent_norm"] = _minmax(merged["intent_proxy"])
    merged["competition_norm"] = _minmax(merged["comp_combined"])
    merged["score"] = 100.0 * (w_int * merged["intent_norm"] + w_cmp * (1.0 - merged["competition_norm"]))

    # -------- Deduplicate before output --------
    merged = _dedupe(merged)

    # -------- Output --------
    out_cols = [c for c in [
        "seed",
        "keyword",
        "keyword_sanitized",
        "comp_coupang" if "comp_coupang" in merged.columns else None,
        "comp_naver" if "comp_naver" in merged.columns else None,
        "comp_combined",
        "intent_proxy",
        "intent_norm",
        "competition_norm",
        "score",
    ] if c is not None]
    out_df = merged[out_cols].copy()
    out_df = out_df.sort_values(
        ["seed" if "seed" in out_df.columns else "score", "score"],
        ascending=[True, False] if "seed" in out_df.columns else [False]
    )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("[OK] Saved CSV:", out_csv)

    if out_xlsx:
        out_xlsx.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as xw:
            out_df.to_excel(xw, index=False, sheet_name="scores")
            ws = xw.sheets["scores"]
            ws.autofilter(0, 0, len(out_df), len(out_df.columns) - 1)
            for i, col in enumerate(out_df.columns):
                width = max(12, min(40, int(out_df[col].astype(str).str.len().quantile(0.9)) + 2))
                ws.set_column(i, i, width)
        print("[OK] Saved XLSX:", out_xlsx)

    if html_out:
        topn = int(max(1, topn))
        top_df = out_df.head(topn)
        html = [
            "<html><head><meta charset='utf-8'><title>Keyword Score Report</title>",
            "<style>body{font-family:sans-serif} table{border-collapse:collapse} th,td{border:1px solid #ddd;padding:6px} th{background:#f6f8fa}</style>",
            "</head><body>",
            f"<h2>Keyword Score Report (Top {topn})</h2>",
            "<p>Weights: W_intent={:.2f}, W_competition={:.2f}</p>".format(w_int, w_cmp),
            top_df.to_html(index=False, escape=False),
            "</body></html>",
        ]
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text("\n".join(html), encoding="utf-8")
        print("[OK] Saved HTML:", html_out)


# ---------- CLI ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel-in", type=Path, required=True, help="Excel file with 'seeds' and 'config' sheets")
    ap.add_argument("--sanitized-in", type=Path, help="CSV of sanitized keywords")
    ap.add_argument("--expanded-in", type=Path, help="CSV of expanded keywords (preferred)")
    ap.add_argument("--competition-in", type=Path, help="CSV of competition counts (optional)")
    ap.add_argument("--out-csv", type=Path, required=True, help="Output CSV path")
    ap.add_argument("--out-xlsx", type=Path, help="Output XLSX path")
    ap.add_argument("--html-out", type=Path, help="Optional HTML report path")
    ap.add_argument("--topn", type=int, default=50, help="Top-N rows for HTML report")
    args = ap.parse_args()

    compute_scores(
        excel_in=args.excel_in,
        sanitized_in=args.sanitized_in,
        expanded_in=args.expanded_in,
        competition_in=args.competition_in,
        out_csv=args.out_csv,
        out_xlsx=args.out_xlsx,
        html_out=args.html_out,
        topn=args.topn,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
