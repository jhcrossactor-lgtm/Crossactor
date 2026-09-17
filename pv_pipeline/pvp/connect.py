"""`python run.py connect` — ChatGPT Image（OpenAI画像API）との疎通確認。

キーの有無 → ホストへの到達性 → モデルの利用可否 → （任意で）実際の1枚編集、
の順に切り分けて、どこで止まっているかを言い切る。
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .providers.openai_image import (
    ProxyBlockedError,
    explain_http_error,
    post_images_edit,
    validate_size,
)
from .util import Project, RunLogger

OK = "OK "
NG = "NG "
WARN = "-- "


def _models_endpoint(edit_endpoint: str) -> str:
    parts = urlsplit(edit_endpoint)
    return f"{parts.scheme}://{parts.netloc}/v1/models"


def _test_images(project: Project) -> list[Path]:
    """疎通確認用の小さな画像を作る。実素材があればそれを縮小して使う。"""
    from PIL import Image

    work = project.log_dir / "connect"
    work.mkdir(parents=True, exist_ok=True)
    target = work / "smoke_input.png"
    Image.new("RGB", (1024, 576), (90, 120, 160)).save(target)
    return [target]


def run_connect(project: Project, logger: RunLogger, smoke: bool = False) -> int:
    config = project.config
    section = dict(config.get("image") or {})
    provider = section.get("provider", "openai")
    endpoint = section.get("endpoint", "https://api.openai.com/v1/images/edits")
    model = section.get("model", "")
    size = section.get("size", "")
    quality = section.get("quality", "high")
    auth = section.get("auth", "bearer")
    key_env = section.get("api_key_env", "OPENAI_API_KEY")
    timeout = int(section.get("timeout_sec", 600))
    host = urlsplit(endpoint).netloc

    print("=" * 64)
    print(" ChatGPT Image 連携チェック")
    print("=" * 64)
    print(f"  provider : {provider}")
    print(f"  endpoint : {endpoint}")
    print(f"  model    : {model}")
    print(f"  size     : {size}")
    print(f"  quality  : {quality}")
    print(f"  auth     : {auth}"
          + ("（プロキシがキーを注入する。セッション側にキーは不要）" if auth == "proxy" else ""))
    print()

    failures = 0

    # 1) size の妥当性 -------------------------------------------------- #
    problems = validate_size(size)
    if problems:
        print(f"{NG}size が不正")
        for p in problems:
            print(f"     - {p}")
        failures += 1
    else:
        print(f"{OK}size {size} は制約を満たしている")

    # 2) APIキー -------------------------------------------------------- #
    if auth == "proxy":
        print(f"{WARN}APIキー: auth=proxy のためセッション側では確認しない")
        headers: dict[str, str] = {}
    else:
        key = os.environ.get(key_env, "").strip()
        if key:
            print(f"{OK}APIキー {key_env} を読み込んだ（末尾4桁 ...{key[-4:]}）")
            headers = {"Authorization": f"Bearer {key}"}
        else:
            print(f"{NG}APIキー {key_env} が未設定。.env に書くこと")
            failures += 1
            headers = {}

    # 3) ホストへの到達性とモデル一覧 ------------------------------------ #
    models_url = _models_endpoint(endpoint)
    try:
        resp = requests.get(models_url, headers=headers, timeout=30)
    except requests.exceptions.ProxyError:
        print(f"{NG}{host} に到達できない（エージェントプロキシが拒否）")
        print("     → クラウド環境のネットワーク設定でこのホストを許可するか、ローカルで実行すること")
        print("     → 詳しくは README の「ChatGPT Image と繋ぐ」を読むこと")
        logger.log(f"connect: {host} egress blocked", host=host, result="blocked")
        return 1
    except requests.exceptions.RequestException as exc:
        print(f"{NG}{host} への接続に失敗: {exc}")
        logger.log(f"connect: {host} 接続失敗 {exc}", host=host, result="error")
        return 1

    if resp.status_code >= 400:
        print(f"{NG}モデル一覧の取得に失敗")
        print("     " + explain_http_error(resp.status_code, resp.text).replace("\n", "\n     "))
        logger.log(f"connect: models {resp.status_code}", result="http_error")
        return 1

    print(f"{OK}{host} に到達。認証も通った")
    ids = sorted(m.get("id", "") for m in (resp.json().get("data") or []))
    image_models = [m for m in ids if "image" in m]
    if image_models:
        print(f"{OK}このアカウントで使える画像モデル {len(image_models)} 件:")
        for m in image_models:
            mark = " ← config.yaml の設定" if m == model else ""
            print(f"       {m}{mark}")
    else:
        print(f"{WARN}画像モデルが一覧に出てこない（一覧に載らない場合もある）")

    if model and model not in ids:
        print(f"{WARN}設定中の {model} は一覧に無い。使えるものに差し替えるか、")
        print("     --smoke で実際に叩けるか確かめること")

    logger.log("connect: 疎通OK", host=host, models=image_models, configured=model)

    # 4) 実際に1枚編集してみる ------------------------------------------ #
    if smoke:
        if failures:
            print("\n先に上の NG を解消すること。--smoke は実行しない")
            return 1
        print("\n--- 実際に1枚編集する（課金が発生する）---")
        images = _test_images(project)
        data = {"model": model, "size": size, "n": "1",
                "prompt": "この画像の色味はそのままに、中央に小さな白い円をひとつ描く。他は変更しない。"}
        if quality:
            data["quality"] = quality
        started = time.time()
        try:
            payload = post_images_edit(endpoint, headers, data, images, timeout)
        except ProxyBlockedError as exc:
            print(f"{NG}{exc}")
            return 1
        except Exception as exc:
            print(f"{NG}編集リクエストが失敗")
            print("     " + str(exc).replace("\n", "\n     "))
            logger.log(f"connect smoke 失敗: {exc}", result="smoke_failed")
            return 1
        out = project.log_dir / "connect" / "smoke_output.png"
        out.write_bytes(base64.b64decode(payload["data"][0]["b64_json"]))
        print(f"{OK}編集成功 {time.time() - started:.1f}秒 -> {out}")
        usage = payload.get("usage") or {}
        if usage:
            print(f"     usage: {usage}")
        logger.log(f"connect smoke OK -> {out}", result="smoke_ok", usage=usage)

    print()
    if failures:
        print(f"未解決 {failures} 件。上の NG を潰すこと")
        return 1
    print("連携OK。`python run.py --stage 1` を回してよい"
          if smoke else "疎通OK。実際に1枚試すなら `python run.py connect --smoke`")
    return 0
