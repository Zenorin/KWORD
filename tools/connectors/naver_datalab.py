import os, json, datetime
from ..common.http import HttpClient
from ..common.env import get_env

def search_trend(keywords):
    base = "https://openapi.naver.com/v1/datalab/search"
    h = {
        "X-Naver-Client-Id": get_env("NAVER_CLIENT_ID", True),
        "X-Naver-Client-Secret": get_env("NAVER_CLIENT_SECRET", True),
        "Content-Type": "application/json",
    }
    body = {
        "startDate": (datetime.date.today()-datetime.timedelta(days=365)).isoformat(),
        "endDate": datetime.date.today().isoformat(),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
    }
    client = HttpClient()
    r = client.post(base, headers=h, json=body)
    return r.json()
