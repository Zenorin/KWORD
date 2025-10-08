#!/usr/bin/env bash
set -euo pipefail
echo "[KWORD Pro] mode=snapshot by default. Use configs/pro.yaml to switch."
echo "1) Collect -> 2) Features -> 3) Rank -> 4) Report -> 5) Verify"
bash "$(dirname "$0")/p1_collect.sh"
bash "$(dirname "$0")/p2_features.sh"
bash "$(dirname "$0")/p3_rank.sh"
bash "$(dirname "$0")/px_report.sh"
bash "$(dirname "$0")/px_verify.sh"
