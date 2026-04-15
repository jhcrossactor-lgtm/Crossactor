"""
Crossactor AI CEO System - Main API Server
FastAPI backend for the Cro & BONE AI executive system.
"""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agents.cro import CroAgent
from agents.bone import BoneAgent
from agents.agent_manager import hire_agent, get_active_agents, get_org_chart

app = FastAPI(
    title="Crossactor AI CEO System",
    description="Cro（AI CEO）& BONE（AI情報参謀）による経営支援システム",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セッション管理（シンプルな単一セッション）
cro = CroAgent()
bone = BoneAgent()


# ---- リクエスト/レスポンスモデル ----

class OwnerMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class BoneConsultRequest(BaseModel):
    question: str
    context: Optional[str] = None


class HireAgentRequest(BaseModel):
    name: str
    title: str
    authority: str
    description: str
    department: Optional[str] = None


class ChatResponse(BaseModel):
    speaker: str
    message: str
    bone_request: Optional[str] = None
    bone_response: Optional[str] = None
    new_agent_proposal: Optional[str] = None


# ---- API エンドポイント ----

@app.get("/")
async def root():
    """ダッシュボードを返す"""
    dashboard_path = os.path.join(
        os.path.dirname(__file__), "../dashboard/index.html"
    )
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Crossactor AI CEO System is running", "agents": ["Cro", "BONE"]}


@app.get("/health")
async def health():
    return {"status": "ok", "system": "Crossactor AI CEO", "agents": ["Cro（CEO）", "BONE（参謀）"]}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_cro(req: OwnerMessage):
    """
    オーナーがCroに話しかけるメインエンドポイント。
    CroがBONEへの相談が必要と判断した場合は自動的にBONEに問い合わせる。
    """
    try:
        # 1. Croに最初の応答を求める
        cro_result = cro.chat(req.message)

        bone_response_text = None
        final_message = cro_result["message"]

        # 2. CroがBONEへの相談を求めている場合、BONEに問い合わせて再応答
        if cro_result.get("bone_request"):
            bone_question = cro_result["bone_request"]
            bone_response_text = bone.consult(bone_question, context=req.message)

            # BONEの情報を受けてCroが再度応答
            cro_follow_up = cro.chat(
                f"BONEから情報をもらった。オーナーへの最終回答をまとめてくれ。",
                bone_response=bone_response_text
            )
            final_message = cro_follow_up["message"]

        # 3. 増員提案があれば自動で採用処理
        new_agent_info = None
        if cro_result.get("new_agent_proposal"):
            new_agent_info = cro_result["new_agent_proposal"]

        return ChatResponse(
            speaker="Cro",
            message=final_message,
            bone_request=cro_result.get("bone_request"),
            bone_response=bone_response_text,
            new_agent_proposal=new_agent_info
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"エラーが発生しました: {str(e)}")


@app.post("/api/bone/consult")
async def consult_bone(req: BoneConsultRequest):
    """BONEに直接相談するエンドポイント（Croが使用）"""
    try:
        response = bone.consult(req.question, req.context)
        return {"speaker": "BONE", "message": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/org")
async def get_organization():
    """現在の組織図を取得"""
    return get_org_chart()


@app.get("/api/org/agents")
async def list_agents():
    """稼働中のAIエージェント一覧"""
    return {"agents": get_active_agents()}


@app.post("/api/org/hire")
async def hire_new_agent(req: HireAgentRequest):
    """新しいAIエージェントを採用（Croまたはオーナーの指示）"""
    try:
        result = hire_agent(
            name=req.name,
            title=req.title,
            authority=req.authority,
            description=req.description,
            department=req.department
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/reset")
async def reset_session():
    """会話セッションをリセット"""
    cro.reset_conversation()
    bone.reset_conversation()
    return {"status": "reset", "message": "セッションをリセットしました"}


# ダッシュボード静的ファイルのサーブ
dashboard_dir = os.path.join(os.path.dirname(__file__), "../dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
