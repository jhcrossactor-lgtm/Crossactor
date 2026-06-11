// slack.gs - Slack Incoming Webhook送信

function sendToSlack(report, timestamp) {
  const config = getConfig();
  if (!config.SLACK_WEBHOOK_URL) throw new Error('SLACK_WEBHOOK_URL が未設定です');

  const blocks = buildSlackBlocks(report, timestamp);
  const payload = {
    text: '📊 関西住宅市場インテリジェンスレポート (' + timestamp + ')',
    blocks: blocks,
  };

  const res = UrlFetchApp.fetch(config.SLACK_WEBHOOK_URL, {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const code = res.getResponseCode();
  if (code !== 200) throw new Error('Slack送信失敗 (' + code + '): ' + res.getContentText());
  Logger.log('Slack送信完了');
}

function buildSlackBlocks(report, timestamp) {
  const blocks = [
    {
      type: 'header',
      text: { type: 'plain_text', text: '📊 関西住宅市場インテリジェンスレポート', emoji: true },
    },
    {
      type: 'context',
      elements: [{
        type: 'mrkdwn',
        text: '*生成日時:* ' + timestamp + '　|　*対象:* 大阪・兵庫・京都・滋賀・奈良・和歌山',
      }],
    },
    { type: 'divider' },
  ];

  // サマリーブロック
  if (report.summary) {
    blocks.push({
      type: 'section',
      text: { type: 'mrkdwn', text: '*📝 今週のサマリー*\n' + report.summary },
    });
    blocks.push({ type: 'divider' });
  }

  // 5カテゴリ
  const categories = [
    { key: 'macro',     emoji: '🏗️', label: '① マクロ市況（着工統計・金利・コスト）' },
    { key: 'corporate', emoji: '🏢', label: '② 企業戦略（IR・決算・用地取得）' },
    { key: 'sales',     emoji: '📈', label: '③ 実売データ（価格・成約動向）' },
    { key: 'leading',   emoji: '🔮', label: '④ 先行指標（建確・住産新聞）' },
    { key: 'field',     emoji: '💬', label: '⑤ 現場の生の声（X・RSS）' },
  ];

  categories.forEach(function(cat) {
    const content = report[cat.key] || '（データ取得中）';
    blocks.push(
      {
        type: 'section',
        text: { type: 'mrkdwn', text: '*' + cat.emoji + ' ' + cat.label + '*' },
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: truncateText(content, 2900) },
      },
      { type: 'divider' }
    );
  });

  blocks.push({
    type: 'context',
    elements: [{
      type: 'mrkdwn',
      text: '🤖 Powered by *Gemini 2.5 Flash* / *Perplexity Sonar* / *Grok 2* / *Claude Sonnet* | kansai-housing-intel',
    }],
  });

  return blocks;
}

function sendErrorToSlack(message) {
  const config = getConfig();
  if (!config.SLACK_WEBHOOK_URL) return;
  UrlFetchApp.fetch(config.SLACK_WEBHOOK_URL, {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify({ text: '❌ *kansai-housing-intel エラー*\n' + message }),
    muteHttpExceptions: true,
  });
}

function truncateText(text, maxLength) {
  if (!text || text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + '...';
}
