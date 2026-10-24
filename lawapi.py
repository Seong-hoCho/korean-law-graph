"""법제처 Open API(DRF) 호출 + 디스크 캐시."""
import hashlib
import os
import json
import pathlib
import time
import urllib.parse
import urllib.request

BASE = "https://www.law.go.kr/DRF"
OC = os.environ.get("LAW_OC", "test")  # 법제처 Open API 인증값(신청한 이메일 ID). 없으면 공개 테스트값
CACHE = pathlib.Path(__file__).parent / "data" / "raw"
CACHE.mkdir(parents=True, exist_ok=True)


def call(endpoint, **params):
    params = {"OC": OC, "type": "JSON", **params}
    url = f"{BASE}/{endpoint}.do?" + urllib.parse.urlencode(params)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    path = CACHE / f"{endpoint}_{params.get('target')}_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                text = r.read().decode("utf-8")
            data = json.loads(text)
            path.write_text(text, encoding="utf-8")
            time.sleep(0.2)
            return data
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(2)


def search(target, query, **params):
    return call("lawSearch", target=target, query=query, **params)


def service(target, **params):
    return call("lawService", target=target, **params)


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]
