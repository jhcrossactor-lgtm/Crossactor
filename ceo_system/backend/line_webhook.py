"""
LINE Webhook Handler
LINEからオーナーの指示を受け取り、Croに渡して返答するモジュール。
"""

import os
from fastapi import APIRouter, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

router = APIRouter()

# LINE 設定
configuration = Configuration(
    access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
)
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET", ""))

# Cro エージェントは main.py から注入する
_cro_agent = None
_bone_agent = None


def init_agents(cro, bone):
    """main.py からエージェントを注入する"""
    global _cro_agent, _bone_agent
    _cro_agent = cro
    _bone_agent = bone


@router.post("/api/line/webhook")
async def line_webhook(request: Request):
    """LINEからのWebhookを受け取るエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return {"status": "ok"}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    """テキストメッセージを受け取ってCroに渡し、LINEに返信する"""
    owner_message = event.message.text

    if not _cro_agent:
        reply_text = "システムが起動していません。しばらく待ってから再度お試しください。"
    else:
        try:
            # Croに指示を渡す
            cro_result = _cro_agent.chat(owner_message)
            bone_response_text = None
            final_message = cro_result["message"]

            # BONEへの相談が必要な場合
            if cro_result.get("bone_request") and _bone_agent:
                bone_question = cro_result["bone_request"]
                bone_response_text = _bone_agent.consult(
                    bone_question, context=owner_message
                )
                cro_follow_up = _cro_agent.chat(
                    "BONEから情報をもらった。オーナーへの最終回答をまとめてくれ。",
                    bone_response=bone_response_text,
                )
                final_message = cro_follow_up["message"]

            # LINE は1メッセージ5000文字制限
            reply_text = final_message[:4900]

            # BONEに相談した場合は一言添える
            if bone_response_text:
                reply_text = "【BONEに確認済み】\n" + reply_text

        except Exception as e:
            reply_text = f"処理中にエラーが発生しました：{str(e)}"

    # LINEに返信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
