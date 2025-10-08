# Build feature table from connector outputs (skeleton)
def build_feature_row(keyword, naver_total=None, price_band=None, coupang_cat=None):
    return {
        "keyword": keyword,
        "naver_total": naver_total or 0,
        "price_band": price_band or "",
        "coupang_category": coupang_cat or "",
    }
