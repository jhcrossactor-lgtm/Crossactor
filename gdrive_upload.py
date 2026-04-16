#!/usr/bin/env python3
"""
Google Drive アップロードスクリプト (純粋requests版)
対象フォルダ: マイドライブ/Crossactor/Crossactor AI Com
"""

import os
import sys
import json
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from requests_oauthlib import OAuth2Session

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
# 正しいフォルダID: マイドライブ/Crossactor/Crossactor AI Com
TARGET_FOLDER_ID = "172si3a_aAEYYHWy8nyYDn9R1aCiVZvbx"
MD_FOLDER_ID = "1fqd0-uZe_UECPQzmmotUmocjDjoHNfAg"  # Crossactor AI Com/md/
DRIVE_FOLDER_PATH = ["Crossactor", "Crossactor AI Com"]

SCOPES = ["https://www.googleapis.com/auth/drive"]
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def load_credentials():
    with open(CREDENTIALS_FILE) as f:
        data = json.load(f)
    return data["installed"]


def load_token():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)


def refresh_access_token(creds, token):
    """リフレッシュトークンで新しいアクセストークンを取得"""
    resp = requests.post(TOKEN_URL, data={
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    new_token = resp.json()
    token["access_token"] = new_token["access_token"]
    save_token(token)
    return token


def authenticate():
    """OAuth2認証フロー（ブラウザ不要・コード貼り付け方式）"""
    creds = load_credentials()

    # 既存トークンを確認
    token = load_token()
    if token:
        # アクセストークンの有効確認
        test = requests.get(
            "https://www.googleapis.com/drive/v3/about?fields=user",
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )
        if test.status_code == 200:
            return token
        # 期限切れならリフレッシュ
        if "refresh_token" in token:
            try:
                return refresh_access_token(creds, token)
            except Exception:
                pass

    # 新規認証
    oauth = OAuth2Session(
        creds["client_id"],
        scope=SCOPES,
        redirect_uri=creds["redirect_uris"][0],
    )
    auth_url, _ = oauth.authorization_url(AUTH_URL, access_type="offline", prompt="consent")

    print("\n" + "="*60)
    print("【認証が必要です】")
    print("以下のURLをブラウザで開いてGoogleアカウントにログインしてください:")
    print()
    print(auth_url)
    print()
    print("ログイン後に表示される認証コードを貼り付けてください:")
    print("="*60)
    code = input("認証コード: ").strip()

    resp = requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "redirect_uri": creds["redirect_uris"][0],
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    token = resp.json()
    save_token(token)
    print("認証完了。トークンを保存しました。")
    return token


def api_get(url, token, params=None):
    resp = requests.get(url, headers={"Authorization": f"Bearer {token['access_token']}"}, params=params)
    resp.raise_for_status()
    return resp.json()


def api_post_json(url, token, data):
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token['access_token']}", "Content-Type": "application/json"},
        json=data
    )
    resp.raise_for_status()
    return resp.json()


def get_or_create_folder(token, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    result = api_get(
        "https://www.googleapis.com/drive/v3/files",
        token,
        params={"q": query, "fields": "files(id,name)"}
    )
    files = result.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    result = api_post_json("https://www.googleapis.com/drive/v3/files", token, metadata)
    return result["id"]


def get_target_folder_id(token):
    folder_id = None
    for name in DRIVE_FOLDER_PATH:
        folder_id = get_or_create_folder(token, name, folder_id)
    return folder_id


def upload_file(file_path: str):
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"エラー: ファイルが見つかりません: {file_path}")
        sys.exit(1)

    print("認証中...")
    token = authenticate()

    print("アップロード先フォルダを確認中...")
    # MDファイルは専用の md/ フォルダへ
    if file_path.suffix.lower() == ".md":
        folder_id = MD_FOLDER_ID
        print("MDファイル → Crossactor AI Com/md/ に保存")
    else:
        folder_id = get_target_folder_id(token)

    # 既存ファイル確認（同名なら上書き）
    query = f"name='{file_path.name}' and '{folder_id}' in parents and trashed=false"
    result = api_get(
        "https://www.googleapis.com/drive/v3/files",
        token,
        params={"q": query, "fields": "files(id,name)"}
    )
    existing = result.get("files", [])

    with open(file_path, "rb") as f:
        file_data = f.read()

    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/octet-stream",
    }

    if existing:
        file_id = existing[0]["id"]
        resp = requests.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media",
            headers=headers,
            data=file_data
        )
    else:
        # multipart upload
        import email.mime.multipart
        import email.mime.base
        import email.mime.application

        metadata = json.dumps({"name": file_path.name, "parents": [folder_id]})
        boundary = "crossactor_boundary"
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--".encode()

        headers["Content-Type"] = f"multipart/related; boundary={boundary}"
        resp = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers=headers,
            data=body
        )

    resp.raise_for_status()
    action = "更新" if existing else "アップロード"
    print(f"\n{action}完了: {file_path.name}")
    print(f"保存先: マイドライブ/Crossactor/Crossactor AI Com/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python gdrive_upload.py <ファイルパス>")
        print("例:     python gdrive_upload.py acabow_logo.svg")
        sys.exit(1)

    upload_file(sys.argv[1])
