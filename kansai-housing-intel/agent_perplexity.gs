// agent_perplexity.gs - Perplexity sonar（最新WEB情報収集担当）

function buildPerplexityRequest(config) {
  const companies = config.TARGET_COMPANIES.join('、');

  const prompt =
    '関西圏（大阪・兵庫・京都・滋賀・奈良・和歌山）の住宅市場に関する最新情報を収集してください。\n\n' +
    '【必須収集項目】\n' +
    '1. 企業IR・決算情報（' + companies + '）\n' +
    '   ・直近の決算発表・業績修正・上方/下方修正\n' +
    '   ・新規プロジェクト・用地取得・合弁・M&A情報\n' +
    '   ・経営戦略変更（価格戦略・ターゲット変更等）\n\n' +
    '2. 住宅産業メディア情報\n' +
    '   ・住宅新報・住宅産業新聞の主要記事\n' +
    '   ・不動産経済研究所・東京カンテイのデータ\n' +
    '   ・関西圏のマンション・戸建て供給予定棟数\n\n' +
    '3. 政策・規制動向\n' +
    '   ・国交省・各府県の住宅政策・補助金\n' +
    '   ・ZEH・省エネ規制の最新進捗\n' +
    '   ・容積率・用途地域の変更情報\n\n' +
    '【出力形式】\n' +
    '・情報源を明記（社名・媒体名・日付）\n' +
    '・箇条書き5〜8項目\n' +
    '・特に重要な情報は★マーク付き\n' +
    '・500字以内';

  const body = {
    model: config.PERPLEXITY_MODEL,
    messages: [
      {
        role: 'system',
        content: '不動産・住宅業界の専門アナリストとして、最新の市場情報を正確に収集・整理してください。情報源（媒体名・日付）を必ず明記してください。',
      },
      { role: 'user', content: prompt },
    ],
    max_tokens: 1024,
    temperature: 0.2,
    search_recency_filter: 'week',
    return_citations: true,
  };

  return {
    url: config.PERPLEXITY_ENDPOINT,
    method: 'POST',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + config.PERPLEXITY_API_KEY },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  };
}

function parsePerplexityResponse(response) {
  try {
    const code = response.getResponseCode();
    const text = response.getContentText();
    if (code !== 200) {
      Logger.log('Perplexity エラー (' + code + '): ' + text.substring(0, 300));
      return '（Perplexity情報収集エラー: HTTP ' + code + '）';
    }
    const json = JSON.parse(text);
    const content =
      json && json.choices && json.choices[0] && json.choices[0].message && json.choices[0].message.content;
    if (!content) {
      Logger.log('Perplexity レスポンス構造エラー');
      return '（Perplexityからのレスポンスが空です）';
    }
    // 引用URLを末尾に付加
    const citations = json.citations;
    let result = content;
    if (citations && citations.length > 0) {
      result += '\n\n📎 参照: ' + citations.slice(0, 3).join(' / ');
    }
    Logger.log('Perplexity 完了: ' + result.length + '文字');
    return result;
  } catch (e) {
    Logger.log('Perplexity パースエラー: ' + e.message);
    return '（Perplexity レスポンス解析エラー: ' + e.message + '）';
  }
}
