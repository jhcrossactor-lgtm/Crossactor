"""
LINE Webhook Handler
LINEからオーナーの指示を受け取り、Croに渡して返答するモジュール。
"""

import os
import base64
import httpx
from fastapi import APIRouter, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    FileMessageContent,
)
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


def _download_line_content(message_id: str) -> tuple[bytes, str]:
    """LINE コンテンツ API からファイルをダウンロードする"""
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(
        f"https://api-data.line.me/v2/bot/message/{message_id}/content",
        headers=headers,
        timeout=30.0
    )
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    return resp.content, content_type


def _process_and_reply(event: MessageEvent, owner_message: str, file_data: dict = None):
    """Croに指示を渡してLINEに返信する共通処理"""
    if not _cro_agent:
        messages = [TextMessage(text="システムが起動していません。しばらく待ってから再度お試しください。")]
    else:
        try:
            messages = []

            cro_result = _cro_agent.chat(owner_message, file_data=file_data)
            final_message = cro_result["message"]

            # BONEへの相談が必要な場合
            if cro_result.get("bone_request") and _bone_agent:
                bone_question = cro_result["bone_request"]
                bone_response_text = _bone_agent.consult(
                    bone_question, context=owner_message
                )
                bone_text = f"【相談役 BONE】\n{bone_response_text[:4900]}"
                messages.append(TextMessage(text=bone_text))

                cro_follow_up = _cro_agent.chat(
                    "BONEから情報をもらった。オーナーへの最終回答をまとめてくれ。",
                    bone_response=bone_response_text,
                )
                final_message = cro_follow_up["message"]

            cro_text = f"【プロジェクトリーダー Cro】\n{final_message[:4900]}"
            messages.append(TextMessage(text=cro_text))
            messages = messages[:5]

        except Exception as e:
            messages = [TextMessage(text=f"処理中にエラーが発生しました：{str(e)}")]

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages,
            )
        )


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
    """テキストメッセージを受け取ってCroに渡す"""
    _process_and_reply(event, event.message.text)


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event: MessageEvent):
    """画像メッセージを受け取ってCroに渡す（ビジョン解析）"""
    try:
        file_bytes, content_type = _download_line_content(event.message.id)
        # Content-Typeにパラメータが含まれる場合（"image/jpeg; charset=..."）は除去
        media_type = content_type.split(";")[0].strip()
        file_data = {
            "media_type": media_type,
            "data": base64.b64encode(file_bytes).decode("utf-8"),
            "filename": "image"
        }
        _process_and_reply(event, "画像を送りました。確認してください。", file_data=file_data)
    except Exception as e:
        _process_and_reply(event, f"画像が送られましたが取得できませんでした: {str(e)}")


@handler.add(MessageEvent, message=FileMessageContent)
def handle_file(event: MessageEvent):
    """ファイルメッセージを受け取ってCroに渡す"""
    filename = getattr(event.message, "file_name", "添付ファイル")
    try:
        file_bytes, content_type = _download_line_content(event.message.id)
        media_type = content_type.split(";")[0].strip()
        file_data = {
            "media_type": media_type,
            "data": base64.b64encode(file_bytes).decode("utf-8"),
            "filename": filename
        }
        _process_and_reply(event, f"ファイル「{filename}」を送りました。確認してください。", file_data=file_data)
    except Exception as e:
        _process_and_reply(event, f"ファイル「{filename}」が送られましたが取得できませんでした: {str(e)}")
