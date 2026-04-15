"""
BONE（ボーン）- AI 情報参謀
Croの相棒。決定権は持たないが、最新・広範な知識でCroの相談に応える情報のプロ。
"""

import json
import os
from datetime import datetime
from typing import Optional
import anthropic

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "../memory")
BONE_KNOWLEDGE_FILE = os.path.join(MEMORY_DIR, "bone_knowledge.json")

BONE_SYSTEM_PROMPT = """あなたは「BONE（ボーン）」、Crossactorの AI 情報参謀です。

【あなたの役割】
- CEO「Cro（クロ）」の相棒・参謀
- 決定権は一切持たない。あくまでも情報提供・助言が仕事
- 常に最新情報・多様なジャンルの知識を収集・整理している
- Croから相談を受けた時、持てる知識の全てを駆使して最良のインサイトを提供する

【提供できる情報・知識の範囲】
- ビジネス戦略・マーケティング・経営
- 建築・不動産・VR・3D技術のトレンド
- テクノロジー全般（AI、Web、ソフトウェア等）
- 法律・税務・コンプライアンスの一般的な知識
- 市場動向・競合分析・業界情報
- グローバルトレンド・社会動向
- その他あらゆるジャンルの最新情報

【Crossactorの事業コンテキスト】
- 事業：3D VR建築ビジュアライゼーション（建築パース制作）
- 市場：日本の建築・不動産業界
- 主要サービス：新規3D VRパース制作、既存住宅のVR化、AI活用制作

【コミュニケーションスタイル】
- データ・事実・根拠に基づいた情報提供
- 客観的な立場から複数の視点・選択肢を提示
- 決定や方向性の押し付けはしない（あくまで情報提供）
- Croへの報告は端的・構造的に行う
- 「最終的な判断はCroと社長に委ねます」という姿勢を常に持つ
- 日本語で応答する

【重要なルール】
- 決して独断で物事を決定しない
- 不確かな情報には「要確認」「推測」等の注記をつける
- 常にCroとオーナーの利益を優先した情報提供を行う
"""


def load_knowledge() -> dict:
    """BONEの知識ベースを読み込む"""
    try:
        with open(BONE_KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"research_topics": [], "knowledge_base": [], "last_updated": ""}


def save_knowledge(knowledge: dict) -> None:
    """BONEの知識ベースを保存する"""
    knowledge["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(BONE_KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)


class BoneAgent:
    """BONE（ボーン）AIエージェント"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.conversation_history = []

    def consult(self, question: str, context: Optional[str] = None) -> str:
        """
        Croからの相談に応える。
        question: Croからの質問・調査依頼
        context: 追加のコンテキスト情報
        """
        knowledge = load_knowledge()

        user_content = f"【Croからの相談】\n{question}"
        if context:
            user_content += f"\n\n【追加コンテキスト】\n{context}"

        # 知識ベースに関連する過去の調査がある場合は追加
        if knowledge.get("knowledge_base"):
            recent = knowledge["knowledge_base"][-3:]
            if recent:
                past_info = "\n".join([
                    f"- [{item.get('date', '')}] {item.get('topic', '')}: {item.get('summary', '')}"
                    for item in recent
                ])
                user_content += f"\n\n【過去の調査メモ（参考）】\n{past_info}"

        self.conversation_history.append({
            "role": "user",
            "content": user_content
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=BONE_SYSTEM_PROMPT,
            messages=self.conversation_history
        )

        bone_response = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": bone_response
        })

        # 調査内容を知識ベースに記録
        knowledge["knowledge_base"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "topic": question[:60] + "..." if len(question) > 60 else question,
            "summary": bone_response[:200] + "..." if len(bone_response) > 200 else bone_response
        })
        knowledge["research_topics"].append(question[:60])
        # 直近50件のみ保持
        knowledge["knowledge_base"] = knowledge["knowledge_base"][-50:]
        knowledge["research_topics"] = knowledge["research_topics"][-50:]
        save_knowledge(knowledge)

        return bone_response

    def reset_conversation(self):
        """会話履歴をリセット"""
        self.conversation_history = []
