import os, json
from ..common.http import HttpClient
from ..common.env import get_env

def search_shop_total(query: str, topN: int = 10):
    base = "https://openapi.naver.com/v1/search/shop.json"
    h = {
        "X-Naver-Client-Id": get_env("NAVER_CLIENT_ID", True),
        "X-Naver-Client-Secret": get_env("NAVER_CLIENT_SECRET", True),
    }
    client = HttpClient()
    r = client.get(base, params={"query": query, "display": topN}, headers=h)
    data = r.json()
    total = data.get("total", 0)
    items = data.get("items", [])
    return {"total": total, "items": items}
