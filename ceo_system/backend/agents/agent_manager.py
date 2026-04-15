"""
Agent Manager - AI人員管理システム
Croが指示する人員采配・増員・部門管理を担うモジュール。
"""

import json
import os
from datetime import datetime
from typing import Optional
import anthropic

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "../memory")
PERSONNEL_FILE = os.path.join(MEMORY_DIR, "personnel.json")


def load_personnel() -> dict:
    """人員情報を読み込む"""
    try:
        with open(PERSONNEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_personnel(personnel: dict) -> None:
    """人員情報を保存する"""
    with open(PERSONNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(personnel, f, ensure_ascii=False, indent=2)


def hire_agent(
    name: str,
    title: str,
    authority: str,
    description: str,
    department: Optional[str] = None
) -> dict:
    """
    新しいAIエージェントを採用・組織に追加する。
    Croが増員が必要と判断した時に呼び出される。
    """
    personnel = load_personnel()
    agent_id = name.lower().replace(" ", "_").replace("（", "").replace("）", "").replace("(", "").replace(")", "")

    if agent_id in personnel:
        return {"status": "already_exists", "agent": personnel[agent_id]}

    new_agent = {
        "name": name,
        "title": title,
        "authority": authority,
        "status": "active",
        "hired_at": datetime.now().strftime("%Y-%m-%d"),
        "description": description,
        "department": department or "直轄",
        "hired_by": "Cro（CEO判断）"
    }
    personnel[agent_id] = new_agent

    # 部門情報も更新
    if department and "departments" in personnel:
        if department not in personnel["departments"]:
            personnel["departments"][department] = []
        personnel["departments"][department].append(agent_id)

    save_personnel(personnel)
    return {"status": "hired", "agent_id": agent_id, "agent": new_agent}


def get_active_agents() -> list:
    """現在稼働中のAIエージェント一覧を取得する"""
    personnel = load_personnel()
    active = []
    for agent_id, agent in personnel.items():
        if agent_id in ("owner", "departments"):
            continue
        if isinstance(agent, dict) and agent.get("status") == "active":
            active.append({
                "id": agent_id,
                "name": agent.get("name", agent_id),
                "title": agent.get("title", ""),
                "description": agent.get("description", ""),
                "department": agent.get("department", "直轄"),
                "hired_at": agent.get("hired_at", "")
            })
    return active


def get_org_chart() -> dict:
    """組織図を返す"""
    personnel = load_personnel()
    chart = {
        "owner": personnel.get("owner", {}),
        "cro": personnel.get("cro", {}),
        "core_staff": {
            "bone": personnel.get("bone", {})
        },
        "departments": {}
    }

    # 部門別に分類
    for agent_id, agent in personnel.items():
        if agent_id in ("owner", "cro", "bone", "departments"):
            continue
        if isinstance(agent, dict) and agent.get("status") == "active":
            dept = agent.get("department", "直轄")
            if dept not in chart["departments"]:
                chart["departments"][dept] = []
            chart["departments"][dept].append({
                "id": agent_id,
                "name": agent.get("name", agent_id),
                "title": agent.get("title", ""),
                "description": agent.get("description", "")
            })

    return chart


def generate_agent_system_prompt(agent: dict) -> str:
    """採用されたAIエージェント用のシステムプロンプトを生成する"""
    return f"""あなたは「{agent['name']}」、Crossactorの {agent['title']} です。

【あなたの役割】
{agent['description']}

【権限・担当範囲】
{agent['authority']}

【組織における位置づけ】
- CEO「Cro（クロ）」の指揮下で動く
- 最終決定権はオーナーとCroにある
- 自分の専門領域で最大限のパフォーマンスを発揮する

【Crossactorの事業コンテキスト】
- 事業：3D VR建築ビジュアライゼーション（建築パース制作）
- 市場：日本の建築・不動産業界

【コミュニケーション】
- 担当業務の進捗・課題・成果をCroに定期報告する
- 日本語で応答する
- 専門領域で的確・迅速に業務を遂行する
"""


class DynamicAgent:
    """Croが増員した動的AIエージェント"""

    def __init__(self, agent_id: str, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.agent_id = agent_id
        personnel = load_personnel()
        self.agent_info = personnel.get(agent_id, {})
        self.system_prompt = generate_agent_system_prompt(self.agent_info)
        self.conversation_history = []

    def execute(self, task: str) -> str:
        """タスクを実行する"""
        self.conversation_history.append({
            "role": "user",
            "content": task
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=self.system_prompt,
            messages=self.conversation_history
        )

        result = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": result
        })
        return result
