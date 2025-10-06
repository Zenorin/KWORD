# Verification Report — Free Edition

- ✅ Found: sanitized → output/sanitized_keywords.csv
- ✅ Found: expanded → output/expanded_keywords.csv
- ✅ Found: competition → output/competition_counts.csv
- ✅ Found: scores_csv → output/keyword_scores_free.csv
- ✅ Scores XLSX → output/keyword_scores_free.xlsx
- ✅ HTML report → output/report.html

**output/sanitized_keywords.csv** — rows=4
columns=['keyword', 'category', 'keyword_sanitized', 'sanitized_changed', 'keyword_original', 'keyword_sanitized_log', 'removed_words', 'removed_symbols', 'changed']
```
     keyword category keyword_sanitized sanitized_changed keyword_original keyword_sanitized_log removed_words removed_symbols changed
[특가] 기모 원피스!  apparel            기모 원피스              True     [특가] 기모 원피스!             [] 기모 원피스            특가               !    True
 무료 배송 겨울 니트  apparel             겨울 니트              True      무료 배송 겨울 니트                 겨울 니트         무료 배송             nan    True
      기모 원피스  apparel            기모 원피스             False           기모 원피스                기모 원피스           nan             nan   False
```

**output/expanded_keywords.csv** — rows=6
columns=['seed_index', 'seed_original', 'seed_sanitized', 'related_original', 'related_sanitized', 'source', 'rank']
```
seed_index seed_original seed_sanitized related_original related_sanitized        source rank
         1   무료 배송 겨울 니트          겨울 니트         겨울 니트목도리          겨울 니트목도리 naver_suggest    1
         1   무료 배송 겨울 니트          겨울 니트        겨울 니트 원피스         겨울 니트 원피스 naver_suggest    2
         2        기모 원피스         기모 원피스        기모 원피스 잠옷         기모 원피스 잠옷 naver_suggest    1
```

**output/competition_counts.csv** — rows=12
columns=['seed_index', 'seed_sanitized', 'related_sanitized', 'comp_coupang', 'comp_naver', 'comp_combined', 'ts']
```
seed_index seed_sanitized related_sanitized comp_coupang comp_naver comp_combined                        ts
       1.0          겨울 니트          겨울 니트목도리          nan        nan           0.0 2025-10-06T06:15:44+00:00
       1.0          겨울 니트         겨울 니트 원피스          nan        nan           0.0 2025-10-06T06:15:46+00:00
       2.0         기모 원피스         기모 원피스 잠옷          nan        nan           0.0 2025-10-06T06:15:48+00:00
```

**output/keyword_scores_free.csv** — rows=6
columns=['seed', 'keyword', 'keyword_sanitized', 'comp_coupang', 'comp_naver', 'comp_combined', 'intent_proxy', 'intent_norm', 'competition_norm', 'score']
```
seed       keyword keyword_sanitized comp_coupang comp_naver comp_combined intent_proxy intent_norm competition_norm score
   1 naver_suggest     naver_suggest          nan        nan           nan          0.0         0.0              0.0  45.0
   1 naver_suggest     naver_suggest          nan        nan           nan          0.0         0.0              0.0  45.0
   2 naver_suggest     naver_suggest          nan        nan           nan          0.0         0.0              0.0  45.0
```

- ✅ scores.csv columns OK
- Score range: min=45.0, max=45.0