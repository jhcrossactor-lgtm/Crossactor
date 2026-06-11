// agent_grok.gs - Grok 2（X/SNSリアルタイム検知担当）

function buildGrokRequest(config) {
  const areas = config.TARGET_AREAS.join('・');
  const companies = config.TARGET_COMPANIES.join('、');

  const prompt =
    'X（旧Twitter）やSNSで話題になっている関西圏の住宅・不動産に関するリアルタイム情報を分析してください。\n\n' +
    '【対象エリア】' + areas + '\n\n' +
    '【検索キーワード群】\n' +
    '・関西 マンション / 住宅 / 不動産\n' +
    '・' + companies + '\n' +
    '・大阪 新築 / 中古 / 価格高騰\n' +
    '・建売 / 注文住宅 / タワマン 関西\n' +
    '・住宅ローン 金利 / 不動産投資 関西\n\n' +
    '【収集・分析項目】\n' +
    '1. 市場センチメント（強気/中立/弱気の比率を最初に明記）\n' +
    '2. 話題のエリア・駅・物件タイプ\n' +
    '3. ネガティブシグナル（クレーム・トラブル・風評）\n' +
    '4. インフルエンサー・専門家の見解\n' +
    '5. バイラルになっているニュース・出来事\n\n' +
    '【出力形式】\n' +
    '・センチメント指数を冒頭に明記：例「🟢強気60% 🟡中立30% 🔴弱気10%」\n' +
    '・箇条書き5〜7項目\n' +
    '・具体的なポスト内容・アカウント名を可能な範囲で引用\n' +
    '・500字以内';

  const body = {
    model: config.GROK_MODEL,
    messages: [
      {
        role: 'system',
        content:
          'あなたはX（Twitter）のリアルタイムデータにアクセスできるSNS分析専門家です。' +
          '住宅市場の市場センチメントと話題を正確に分析してください。',
      },
      { role: 'user', content: prompt },
    ],
    max_tokens: 1024,
    temperature: 0.3,
  };

  return {
    url: config.GROK_ENDPOINT,
    method: 'POST',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + config.GROK_API_KEY },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  };
}

function parseGrokResponse(response) {
  try {
    const code = response.getResponseCode();
    const text = response.getContentText();
    if (code !== 200) {
      Logger.log('Grok エラー (' + code + '): ' + text.substring(0, 300));
      return '（GrokリアルタイムSNS検知エラー: HTTP ' + code + '）';
    }
    const json = JSON.parse(text);
    const content =
      json && json.choices && json.choices[0] && json.choices[0].message && json.choices[0].message.content;
    if (!content) {
      Logger.log('Grok レスポンス構造エラー');
      return '（Grokからのレスポンスが空です）';
    }
    Logger.log('Grok 完了: ' + content.length + '文字');
    return content;
  } catch (e) {
    Logger.log('Grok パースエラー: ' + e.message);
    return '（Grok レスポンス解析エラー: ' + e.message + '）';
  }
}
