# PRD — KWORD: Keyword Scoring (Free Edition)
## 14. Snapshot — v0.3.0 — 2025-10-07 11:17:52 UTC+09:00
### Regression Snapshot
- Time: 2025-10-08 11:43 UTC+09:00
- Artifacts:
**output/regression/sanitized_keywords.csv** — rows=2

**output/regression/expanded_keywords.csv** — rows=1

**output/regression/competition_counts.csv** — rows=1

**output/regression/keyword_scores_free.csv** — rows=1


**Execution Context**
- Timezone: Asia/Seoul (KST)

**Artifacts**
- ✅ output/sanitized_keywords.csv
- ✅ output/expanded_keywords.csv
- ✅ output/competition_counts.csv
- ✅ output/keyword_scores_free.csv
- ✅ output/keyword_scores_free.xlsx
- ✅ output/report.html

**Commands (latest)**
_Commands not captured; see WBS Cheat Sheet._

**Previews (Top 3)**

**Sanitized** — rows=4 | columns=['keyword', 'category', 'keyword_sanitized', 'sanitized_changed', 'keyword_original', 'keyword_sanitized_log', 'removed_words', 'removed_symbols', 'changed']
```
     keyword category keyword_sanitized sanitized_changed keyword_original keyword_sanitized_log removed_words removed_symbols changed
[특가] 기모 원피스!  apparel         [] 기모 원피스              True     [특가] 기모 원피스!             [] 기모 원피스            특가               !    True
 무료 배송 겨울 니트  apparel             겨울 니트              True      무료 배송 겨울 니트                 겨울 니트         무료 배송             nan    True
      기모 원피스  apparel            기모 원피스             False           기모 원피스                기모 원피스           nan             nan   False
```

**Expanded** — rows=6 | columns=['seed_index', 'seed_original', 'seed_sanitized', 'related_original', 'related_sanitized', 'source', 'rank']
```
seed_index seed_original seed_sanitized related_original related_sanitized        source rank
         1   무료 배송 겨울 니트          겨울 니트         겨울 니트목도리          겨울 니트목도리 naver_suggest    1
         1   무료 배송 겨울 니트          겨울 니트        겨울 니트 원피스         겨울 니트 원피스 naver_suggest    2
         2        기모 원피스         기모 원피스        기모 원피스 잠옷         기모 원피스 잠옷 naver_suggest    1
```

**Competition** — rows=6 | columns=['seed_index', 'seed_sanitized', 'related_sanitized', 'comp_coupang', 'comp_naver', 'comp_combined', 'ts']
```
seed_index seed_sanitized related_sanitized comp_coupang comp_naver comp_combined                        ts
         1          겨울 니트          겨울 니트목도리          nan        nan           0.0 2025-10-07T02:17:38+00:00
         1          겨울 니트         겨울 니트 원피스          nan        nan           0.0 2025-10-07T02:17:40+00:00
         2         기모 원피스         기모 원피스 잠옷          nan        nan           0.0 2025-10-07T02:17:43+00:00
```

**Scores** — rows=3 | columns=['seed', 'keyword', 'keyword_sanitized', 'comp_coupang', 'comp_naver', 'comp_combined', 'intent_proxy', 'intent_norm', 'competition_norm', 'score']
```
seed       keyword keyword_sanitized comp_coupang comp_naver comp_combined intent_proxy intent_norm competition_norm score
   1 naver_suggest     naver_suggest          0.0        0.0           0.0          0.0         0.0              0.0  45.0
   2 naver_suggest     naver_suggest          0.0        0.0           0.0          0.0         0.0              0.0  45.0
   3 naver_suggest     naver_suggest          0.0        0.0           0.0          0.0         0.0              0.0  45.0
```

> Note: previews truncated to 3 rows; see full CSVs in `output/`.
