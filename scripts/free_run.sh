#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PYTHONUNBUFFERED=1 python -u src/keyword_scoring_free_only.py \
  --in data/seeds.xlsx \
  --expand 2 --sleep 0.6 --site-mode naver \
  --sanitized-out output/sanitized_keywords.csv \
  --expanded-out output/expanded_keywords.csv \
  --competition-out output/competition_counts.csv
python -u tools/compute_scores.py \
  --excel-in data/seeds.xlsx \
  --sanitized-in output/sanitized_keywords.csv \
  --expanded-in output/expanded_keywords.csv \
  --competition-in output/competition_counts.csv \
  --out-csv output/keyword_scores_free.csv \
  --out-xlsx output/keyword_scores_free.xlsx \
  --topn 50 --html-out output/report.html
