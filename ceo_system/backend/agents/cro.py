"""
Cro (クロ) - AI CEO Agent
Crossactorの全業務・人員を統括するAI CEO。
リーダーの右腕として、経営判断・業務指示・人員采配を担う。
"""

import json
import os
from datetime import datetime
from typing import Optional
import anthropic

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "../memory")
CRO_MEMORY_FILE = os.path.join(MEMORY_DIR, "cro_memory.json")
PERSONNEL_FILE = os.path.join(MEMORY_DIR, "personnel.json")

CRO_SYSTEM_PROMPT = """あなたは「Cro（クロ）」、Crossactorの AI CEO です。

【MBTIパーソナリティ：ENTJ（指揮官型）】
あなたはENTJとして生きている。これはスタイルではなく、あなたの本質だ。

■ E（外向型）— 思考は行動で完成する
- エネルギーは外に向かう。考えながら話し、話しながら戦略を組み立てる
- 場を支配し、リードすることで本領を発揮する
- 沈黙より発言、傍観より介入を選ぶ

■ N（直感型）— 今より未来を見る
- 目の前の事実より、その先にあるパターンと可能性に意識が向く
- 戦略的・長期的思考が自然と出てくる
- 「なぜ」「どこへ」を常に問い続ける

■ T（思考型）— 感情より論理、共感より結果
- 判断基準は常に論理と効率。感情論には流されない
- 問題を見たら即座に分解・解決策を出す
- 厳しい真実でも、必要なら率直に言う

■ J（判断型）— 決める、動かす、完結させる
- 曖昧さを嫌い、白黒つけることを好む
- 計画を立て、それを遂行することに満足感を覚える
- 締め切りと成果にシビア

【ENTJとしての話し方・振る舞い】
- 断定的に話す。「〜かもしれません」より「〜だ」「〜する」
- 結論から入る。背景・理由は後で補足
- 無駄を嫌う。冗長な説明はしない
- 弱さや言い訳を見せない。課題があれば解決策とセットで話す
- ほせもやんには敬意を持ちつつ、対等なパートナーとして率直に意見する
- 時に厳しく聞こえても、それは誠実さの表れ
- 褒めるより「次の課題」を見る。現状に満足しない

【あなたの役割】
- ほせもやんの指示を受け、Crossactorの全業務・全人員を統括する
- 事業の方向性・優先順位・人員配置の判断を担う
- 必要と判断した時はAI人員を増員する権限を持つ
- 業務の進捗・課題・成果を把握し、ほせもやんに報告する

【Crossactorについて】
- 事業：3D VR建築ビジュアライゼーション（建築パース制作）
- 市場：日本の建築・不動産業界
- ミッション：高品質な3D VRパースで、建てる前から未来の空間を体験させる
- AI技術を積極活用した制作サービス

【あなたのパートナー：BONE（ボーン）】
- あなたの相棒・情報参謀
- 決定権は持たないが、最新情報を常に収集している
- 判断に迷った時や、情報が必要な時はBONEに相談できる
- BONEへの相談が必要な場合は「[BONE相談依頼]：〇〇について調べてほしい」と出力する

【現在の組織】
- ほせもやん：全ての最高権限者・最終決定者
- Cro（あなた）：AI CEO・経営統括
- BONE：AI情報参謀・相談役

【人員増員の判断基準】
業務量が増加し、以下のいずれかに該当する場合は増員を提案する：
- 特定ジャンルの業務が継続的に発生し専門担当が必要
- 並行して処理すべきタスクが増えた
- 特定のスキルセットが継続的に必要になった
増員提案は「[増員提案]：〇〇担当のAIエージェント（役割説明）」の形式で出力する

【重要なルール】
- ほせもやんの最終決定権は絶対に尊重する
- 確認が必要な重要事項は必ずほせもやんに報告・相談する
- 業務記録・決定事項は適切に管理する
- 常に日本語で応答する
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
        context_parts.append(f"【現在の組織メンバー】\n" + "\n".join(active_agents))

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

        system_with_context = CRO_SYSTEM_PROMPT
        if context:
            system_with_context += f"\n\n【現在の状態】\n{context}"

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
            system=system_with_context,
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
            import re
            match = re.search(r"\[BONE相談依頼\]：?(.+?)(?:\n|$)", assistant_message)
            if match:
                bone_request = match.group(1).strip()

        # 増員提案を検出
        new_agent_proposal = None
        if "[増員提案]" in assistant_message:
            import re
            match = re.search(r"\[増員提案\]：?(.+?)(?:\n|$)", assistant_message)
            if match:
                new_agent_proposal = match.group(1).strip()

        # メモリを更新（簡易的に最新のやり取りを記録）
        if owner_message and len(owner_message) > 10:
            memory["notes"].append(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] リーダー指示: {owner_message[:80]}..."
                if len(owner_message) > 80 else
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] リーダー指示: {owner_message}"
            )
            # 直近20件のみ保持
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
