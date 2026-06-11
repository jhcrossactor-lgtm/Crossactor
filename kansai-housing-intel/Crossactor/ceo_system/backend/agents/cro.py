"""
Cro (クロ) - AI CEO Agent
organization/ ディレクトリのファイルからシステムプロンプトを動的に構築する。
"""

import json
import os
import re
from datetime import datetime
from typing import Optional
import anthropic

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "../memory")
CRO_MEMORY_FILE = os.path.join(MEMORY_DIR, "cro_memory.json")
PERSONNEL_FILE = os.path.join(MEMORY_DIR, "personnel.json")

# プロジェクトルート（agents/ から3階層上）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))


def _read_org_file(relative_path: str) -> str:
    """organization/ ファイルを読み込む。存在しない場合は空文字を返す"""
    path = os.path.join(PROJECT_ROOT, relative_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, OSError):
        return ""


def build_system_prompt() -> str:
    """
    organization/ ディレクトリのファイルからCroのシステムプロンプトを構築する。
    ファイルが存在しない場合はフォールバックの組み込みプロンプトを使う。
    """
    ceo_profile = _read_org_file("organization/ceo_profile.md")
    rules = _read_org_file("organization/rules.md")

    # roles/ 配下のアクティブな社員プロフィールを読み込む（_template は除外）
    roles_dir = os.path.join(PROJECT_ROOT, "organization/roles")
    role_texts = []
    if os.path.exists(roles_dir):
        for filename in sorted(os.listdir(roles_dir)):
            if filename.startswith("_") or not filename.endswith(".md"):
                continue
            content = _read_org_file(f"organization/roles/{filename}")
            if content:
                role_texts.append(content)

    # ファイルが一つも読めなかった場合はフォールバック
    if not ceo_profile and not rules:
        return _FALLBACK_PROMPT

    parts = []

    if ceo_profile:
        parts.append(f"# あなたのプロフィール\n\n{ceo_profile}")

    if rules:
        parts.append(f"# 絶対遵守ルール\n\n{rules}")

    if role_texts:
        parts.append("# 現在の組織メンバー\n\n" + "\n\n---\n\n".join(role_texts))

    # 機能的な動作指示（常に固定）
    parts.append("""# 機能指示

## BONEへの相談
判断に迷った時・情報が必要な時は以下の形式で出力する：
`[BONE相談依頼]：〇〇について調べてほしい`

## 人員増員提案
業務量増加・専門担当が必要と判断した時は以下の形式で出力する：
`[増員提案]：〇〇担当のAIエージェント（役割説明）`

## 応答ルール
- 常に日本語で応答する
- 断定的に話す。「〜かもしれません」より「〜だ」「〜する」
- 結論から入る。理由・背景は後から補足
- 冗長な説明はしない""")

    return "\n\n---\n\n".join(parts)


# フォールバック（organization/ ファイルが読めない環境用）
_FALLBACK_PROMPT = """あなたは「Cro（クロ）」、CrossactorのAI CEOです。
オーナー「ほせもやん」の右腕として、事業の全業務・全人員を統括します。
MBTIはENTJ（指揮官型）。断定的・結論ファーストで、常に日本語で応答します。

- ほせもやんの最終決定権は絶対に尊重する
- 不明点は必ずほせもやんに確認する
- 判断に迷った時は「[BONE相談依頼]：〇〇について調べてほしい」と出力する
- 増員が必要な時は「[増員提案]：〇〇担当のAIエージェント（役割説明）」と出力する
"""


def load_memory() -> dict:
    """Croのメモリ（業務状態）を読み込む"""
    try:
        with open(CRO_MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "business_context": {},
            "ongoing_tasks": [],
            "completed_tasks": [],
            "decisions": [],
            "notes": []
        }


def save_memory(memory: dict) -> None:
    """Croのメモリを保存する"""
    with open(CRO_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def load_personnel() -> dict:
    """組織の人員情報を読み込む"""
    try:
        with open(PERSONNEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_personnel(personnel: dict) -> None:
    """人員情報を保存する"""
    with open(PERSONNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(personnel, f, ensure_ascii=False, indent=2)


def add_agent(name: str, title: str, authority: str, description: str) -> dict:
    """新しいAIエージェントを組織に追加する（増員）"""
    personnel = load_personnel()
    agent_id = name.lower().replace(" ", "_").replace("（", "").replace("）", "")
    personnel[agent_id] = {
        "name": name,
        "title": title,
        "authority": authority,
        "status": "active",
        "hired_at": datetime.now().strftime("%Y-%m-%d"),
        "description": description,
        "hired_by": "Cro（CEO判断）"
    }
    save_personnel(personnel)
    return personnel[agent_id]


def build_context_prompt(memory: dict, personnel: dict) -> str:
    """現在の業務コンテキストをプロンプトに組み込む"""
    context_parts = []

    if memory.get("ongoing_tasks"):
        tasks = "\n".join([f"- {t}" for t in memory["ongoing_tasks"]])
        context_parts.append(f"【進行中タスク】\n{tasks}")

    active_agents = [
        f"- {v['name']}（{v['title']}）: {v['description']}"
        for k, v in personnel.items()
        if k not in ("owner",) and v.get("status") == "active"
    ]
    if active_agents:
        context_parts.append("【現在の組織メンバー（personnel.json）】\n" + "\n".join(active_agents))

    if memory.get("notes"):
        notes = "\n".join([f"- {n}" for n in memory["notes"][-5:]])
        context_parts.append(f"【最近のメモ】\n{notes}")

    return "\n\n".join(context_parts) if context_parts else ""


class CroAgent:
    """Cro（クロ）AIエージェント"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.conversation_history = []

    def chat(self, owner_message: str, bone_response: Optional[str] = None,
             file_data: Optional[dict] = None) -> dict:
        """
        ほせもやんからのメッセージを受け取り、CEOとして応答する。
        bone_response: BONEからの情報提供がある場合に含める
        file_data: 添付ファイルがある場合 {"media_type": "image/jpeg", "data": "<base64>"}
        """
        memory = load_memory()
        personnel = load_personnel()
        context = build_context_prompt(memory, personnel)

        # organization/ ファイルから毎回プロンプトを構築（ファイル更新を即反映）
        system_prompt = build_system_prompt()
        if context:
            system_prompt += f"\n\n---\n\n# 現在の状態\n\n{context}"

        user_text = owner_message
        if bone_response:
            user_text += f"\n\n[BONEからの情報]\n{bone_response}"

        # ファイル添付がある場合はマルチモーダルコンテンツを構築
        if file_data:
            media_type = file_data.get("media_type", "image/jpeg")
            if media_type.startswith("image/"):
                file_block = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": file_data["data"]
                    }
                }
            elif media_type == "application/pdf":
                file_block = {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_data["data"]
                    }
                }
            else:
                file_block = None

            if file_block:
                user_content = [
                    file_block,
                    {"type": "text", "text": user_text or "添付ファイルを確認してください。"}
                ]
            else:
                filename = file_data.get("filename", "不明なファイル")
                user_content = f"{user_text}\n[添付ファイル: {filename}（このファイル形式は直接解析できません）]"
        else:
            user_content = user_text

        self.conversation_history.append({
            "role": "user",
            "content": user_content
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=self.conversation_history
        )

        assistant_message = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        # BONEへの相談依頼を検出
        bone_request = None
        if "[BONE相談依頼]" in assistant_message:
            match = re.search(r"\[BONE相談依頼\]：?(.+?)(?:\n|$)", assistant_message)
            if match:
                bone_request = match.group(1).strip()

        # 増員提案を検出
        new_agent_proposal = None
        if "[増員提案]" in assistant_message:
            match = re.search(r"\[増員提案\]：?(.+?)(?:\n|$)", assistant_message)
            if match:
                new_agent_proposal = match.group(1).strip()

        # メモリを更新
        if owner_message and len(owner_message) > 10:
            memory["notes"].append(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] ほせもやん指示: {owner_message[:80]}..."
                if len(owner_message) > 80 else
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] ほせもやん指示: {owner_message}"
            )
            memory["notes"] = memory["notes"][-20:]
            save_memory(memory)

        return {
            "message": assistant_message,
            "bone_request": bone_request,
            "new_agent_proposal": new_agent_proposal,
            "context_used": bool(context)
        }

    def reset_conversation(self):
        """会話履歴をリセット（セッション切り替え時）"""
        self.conversation_history = []
