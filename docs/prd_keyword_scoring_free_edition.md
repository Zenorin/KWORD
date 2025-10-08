PRD — KWORD: Keyword Scoring (Free Edition)
1. Overview

KWORD Free Edition generates and ranks keyword candidates for e‑commerce contexts using seed terms, intent tokens, light sanitization, suggestion-based expansion, lightweight competition signals, and a transparent scoring formula.

2. Goals / Non‑Goals

Goals

Produce a reproducible, local, and dependency-light keyword scoring pipeline.

Allow non-technical users to configure weights/tokens directly in Excel.

Provide deterministic verification (golden snapshot + CI smoke).

Offer a clear report (Report+) for browsing, sorting, and exporting results.

Non‑Goals

Full-scale crawling or paid APIs (Pro scope).

Advanced ML ranking; Free uses deterministic scoring.

3. Users & Stories

Operator (Marketer/PM): Upload seeds, tweak tokens/weights, export top keywords.

Developer: Extend rules, add sources, maintain CI consistency via golden snapshot.

4. Inputs

Excel: data/seeds.xlsx

Sheet seeds: keyword, category (minimum)

Sheet config: W_intent, W_competition; optional token table; optional key/value rows: prohibited_words, prohibited_symbols.

5. Pipeline (Free)

Sanitize → normalize strings, remove prohibited words/symbols (partial-match), log changes → output/sanitized_keywords.csv.

Expand (Naver Suggest) → output/expanded_keywords.csv.

Competition (site-mode selectable; default: naver) → output/competition_counts.csv.

Score (deterministic):

Normalize intent & competition → intent_norm and competition_norm in [0,1].

Weighted sum: score = 100 * (W_intent*intent_norm + W_competition*(1-competition_norm)).

Save to output/keyword_scores_free.csv / .xlsx; optionally output/report.html.

6. Config & Tooling

Intent tokens in config sheet (columns: token, weight, enabled).

Upsert tool: tools/patch_config_tokens.py.

Prohibited lists stored as key/value rows:

prohibited_words, prohibited_symbols (newline-separated in a single cell).

Upsert tool: tools/patch_prohibited_lists.py.

Regression seeds: tools/make_regression_seeds.py → data/seeds_regression.xlsx.

Golden snapshot: tools/make_golden_snapshot.py → output/golden/regression/* + manifest.json.

CI smoke: tools/ci_smoke.py (compares recomputed scores vs golden).

Report+: tools/make_report_plus.py → interactive output/report_plus.html.

Verification: tools/verify_outputs.py (required cols, numeric coercion, score range, duplicates). Optional tools/fix_duplicates.py keeps highest score per key.

7. Scripts (Free)

scripts/free_run.sh — full Free pipeline.

scripts/d6_report_plus.sh — generate Report+ and update PRD/WBS.

scripts/d7_verify.sh — verify → optional auto de-dup → update PRD/WBS.

8. Outputs

output/sanitized_keywords.csv

output/expanded_keywords.csv

output/competition_counts.csv

output/keyword_scores_free.csv / .xlsx

output/report.html / output/report_plus.html

output/_verify_report.md

output/golden/regression/* (golden inputs + keyword_scores_free.csv + manifest.json)

9. Quality & CI

Determinism: Golden snapshot supplies fixed inputs for scoring.

CI: .github/workflows/ci-smoke.yml runs tools/ci_smoke.py with tolerance 1e-9.

Verification: verify_outputs.py ensures schema and ranges; fix_duplicates.py resolves key duplicates.

10. Versioning & Branching

Branches: main = Free; pro = Pro edition.

Tags: free-v0.3.0-snapshot (Free), pro-v0.1.0-snapshot (Pro).

11. Runbook (Operator Rules)

Execute one task at a time from WBS.

After each task completes, pause and request approval before the next.

Mark completed items with - [x] in WBS and reflect changes in PRD Snapshot.

12. Risks & Open Items

Suggest/competition endpoints may throttle; keep --sleep conservative.

If schema drifts, compute_scores.py may need column auto-detection updates.

13. Next (Roadmap)

D7: Verify & auto de-dup (running routinely).

D8: Externalize runtime switches (site-mode, retry, sleep) into config.

14. Snapshot (Updated 2025‑10‑08 KST)

Intent tokens: 10 loaded ✅ — 빅사이즈(1.00), 임산부(0.90), 하객(0.70), 홈웨어(0.60), 니트(0.50), 롱(0.50), 후드(0.40), 맨투맨(0.40), 폴라(0.40), 기모(0.30)

Prohibited lists (configured via config key/value):

words ⊇ ["특가","세일","할인","쿠폰","행사","증정","무료증정","무료배송","정품아님","짝퉁","광고","ad","sponsored"]

symbols ⊇ ["【","】","［","］","『","』","「","」","★","☆","♡","❤","♥","※","❗","❕","❌","✔"]

Regression Snapshot: present at output/regression/ (sanitized / expanded / competition / scores / report.html)

Golden Snapshot: present at output/golden/regression/ with manifest.json (sha256 + row/col counts)

Report+: output/report_plus.html (search/sort/export)

CI Smoke: configured (.github/workflows/ci-smoke.yml → tools/ci_smoke.py)

Versioning: branch pro, tags free-v0.3.0-snapshot, pro-v0.1.0-snapshot

## Snapshot
**Report+:** generated ✅ — 2025-10-08 19:05 UTC+09:00 (output/report_plus.html)
