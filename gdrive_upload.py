#!/usr/bin/env python3
"""
Google Drive アップロードスクリプト
対象フォルダ: マイドライブ/Crossactor/Crossactor AI Com
"""

import os
import sys
import json
from pathlib import Path

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
DRIVE_FOLDER_PATH = ["Crossactor", "Crossactor AI Com"]


def get_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, folder_name, parent_id=None):
    """フォルダを取得または作成する"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def get_target_folder_id(service):
    """Crossactor/Crossactor AI Com フォルダのIDを取得"""
    folder_id = None
    for folder_name in DRIVE_FOLDER_PATH:
        folder_id = get_or_create_folder(service, folder_name, folder_id)
    return folder_id


def upload_file(file_path: str):
    """指定ファイルをGoogle Driveにアップロード"""
    from googleapiclient.http import MediaFileUpload

    file_path = Path(file_path)
    if not file_path.exists():
        print(f"エラー: ファイルが見つかりません: {file_path}")
        sys.exit(1)

    print(f"認証中...")
    service = get_service()

    print(f"アップロード先フォルダを確認中...")
    folder_id = get_target_folder_id(service)

    # 既存ファイルの確認（同名ファイルがあれば上書き）
    query = f"name='{file_path.name}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    existing = results.get("files", [])

    media = MediaFileUpload(str(file_path), resumable=True)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"更新完了: {file_path.name} → マイドライブ/Crossactor/Crossactor AI Com/")
    else:
        metadata = {"name": file_path.name, "parents": [folder_id]}
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        print(f"アップロード完了: {file_path.name} → マイドライブ/Crossactor/Crossactor AI Com/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python gdrive_upload.py <ファイルパス>")
        print("例:     python gdrive_upload.py acabow_logo.svg")
        sys.exit(1)

    upload_file(sys.argv[1])
