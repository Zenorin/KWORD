#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERR] ${BASH_SOURCE[0]}:${LINENO}: ${BASH_COMMAND} (exit=$?)" >&2' ERR
cd "$(dirname "$0")/.."

# 1) Report+ 생성
python -u tools/make_report_plus.py --topn 50 --per-seed 10

# 2) PRD 스냅샷에 Report+ 메모 추가
python - <<'PY'
from pathlib import Path
import re, datetime as dt
prd = Path("docs/prd_keyword_scoring_free_edition.md")
txt = prd.read_text(encoding="utf-8").splitlines()
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M %Z")
inserted=False
for i, line in enumerate(txt):
    if re.match(r'^\s*##\s*(?:14\.\s*)?Snapshot\b', line, flags=re.I):
        j=i+1
        if j < len(txt) and txt[j].strip().lower().startswith("**report+:**"):
            txt.pop(j)
        txt.insert(i+1, f"**Report+:** generated ✅ — {now} (output/report_plus.html)")
        inserted=True
        break
if not inserted:
    txt.extend(["","## Snapshot",f"**Report+:** generated ✅ — {now} (output/report_plus.html)"])
prd.write_text("\n".join(txt)+"\n", encoding="utf-8")
print("[OK] PRD note updated")
PY

# 3) WBS D6 체크 (있으면 체크, 없으면 추가)
python - <<'PY'
import re, pathlib
wbs = pathlib.Path("docs/wbs_keyword_scoring_free_edition.md")
s = wbs.read_text(encoding="utf-8")
if re.search(r"^- \[ \] D6\.", s, flags=re.M):
    s = re.sub(r"^- \[ \] D6\.", "- [x] D6.", s, flags=re.M)
elif re.search(r"^##\s*Epic D", s, flags=re.M):
    s = re.sub(r"(##\s*Epic D[^\n]*\n)", r"\1- [x] D6. Report+ dashboard generated\n", s, flags=re.M)
else:
    s += "\n\n## Epic D — Data & Config Quality\n- [x] D6. Report+ dashboard generated\n"
wbs.write_text(s, encoding="utf-8")
print("[OK] WBS D6 checked/added")
PY

# 4) 커밋
git add tools/make_report_plus.py scripts/d6_report_plus.sh docs/*.md output/report_plus.html 2>/dev/null || true
git commit -m "feat(free): D6 Report+ (search/sort/export) + PRD/WBS updates" || true
echo "[DONE] D6 Report+ finalized."
