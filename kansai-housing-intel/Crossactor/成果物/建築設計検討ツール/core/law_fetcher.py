"""e-Gov 法令APIから建築基準法・民法の条文を取得してキャッシュする"""
import json
import hashlib
import httpx
from pathlib import Path
from datetime import datetime

from config import EGOV_API_BASE, LAW_IDS, LAW_CACHE_DIR


def _cache_path(law_name: str) -> Path:
    return LAW_CACHE_DIR / f"{law_name}.json"


def _meta_path(law_name: str) -> Path:
    return LAW_CACHE_DIR / f"{law_name}_meta.json"


def fetch_law(law_name: str, force_refresh: bool = False) -> dict:
    cache = _cache_path(law_name)
    if cache.exists() and not force_refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    law_id = LAW_IDS[law_name]
    url = f"{EGOV_API_BASE}/lawdata/{law_id}"

    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    LAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _meta_path(law_name).write_text(json.dumps({
        "fetched_at": datetime.now().isoformat(),
        "law_id": law_id,
        "hash": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
    }, ensure_ascii=False), encoding="utf-8")

    return data
