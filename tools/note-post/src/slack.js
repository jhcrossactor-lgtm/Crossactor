import { config } from './config.js';

export async function notifySlack(text) {
  if (!config.slackWebhook) {
    console.error('[slack] SLACK_WEBHOOK_URL未設定のため通知スキップ:', text);
    return;
  }
  try {
    const res = await fetch(config.slackWebhook, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text: `[note-post] ${text}` }),
    });
    if (!res.ok) console.error('[slack] 通知失敗 HTTP', res.status);
  } catch (e) {
    console.error('[slack] 通知失敗', e.message);
  }
}
