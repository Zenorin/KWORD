# PRD — KWORD: Keyword Scoring (Pro Edition)

## 1. Overview
- 목적: Free Edition 파이프라인을 기반으로 Pro 기능(멀티 소스 경쟁도, 사용자 사전, 배치/리트라이 강화, 리포트+) 제공

## 2. Scope (v0.1.0)
- [In] Free 파이프라인 호환, Pro 전용 config 확장
- [Out] 유료 API/크롤링은 미포함(추후)
## 14. Snapshot — v0.3.0 — 2025-10-08 15:24:36 UTC+09:00
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
