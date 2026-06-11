// agent_gemini.gs - Gemini 2.5 Flash（マクロデータ分析担当）

function buildGeminiRequest(config, rssData) {
  const endpoint =
    config.GEMINI_ENDPOINT + config.GEMINI_MODEL + ':generateContent?key=' + config.GEMINI_API_KEY;

  const rssContext = rssData && rssData.length > 0
    ? '\n\n【収集済みRSSニュース（参考）】\n' + formatRssForReport(rssData).substring(0, 2000)
    : '';

  const prompt = 'あなたは関西圏住宅市場の定量分析専門家です。\n' +
    '以下の観点で現状を分析し、構造化されたレポートを作成してください。\n\n' +
    '【分析対象エリア】大阪・兵庫・京都・滋賀・奈良・和歌山\n\n' +
    '【分析観点】\n' +
    '1. e-Stat 新設住宅着工統計のトレンド\n' +
    '   ・戸建て・マンション・貸家別の着工動向\n' +
    '   ・関西6府県の前年比較と全国との乖離\n' +
    '2. 住宅価格指数の動向（新築・中古）\n' +
    '3. 金利上昇・建材コスト・人件費が需要に与える影響\n' +
    '4. 関西圏特有のリスク・機会要因（万博レガシー、うめきた2期 等）\n' +
    rssContext + '\n\n' +
    '【出力形式】\n' +
    '・箇条書きで要点を整理（5〜7項目）\n' +
    '・数値がある場合は必ず記載\n' +
    '・最後に「注目ポイント」を1つ記載\n' +
    '・全体500字以内';

  const body = {
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.3, maxOutputTokens: 1024 },
  };

  return {
    url: endpoint,
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  };
}

function parseGeminiResponse(response) {
  try {
    const code = response.getResponseCode();
    const text = response.getContentText();
    if (code !== 200) {
      Logger.log('Gemini エラー (' + code + '): ' + text.substring(0, 300));
      return '（Gemini分析エラー: HTTP ' + code + '）';
    }
    const json = JSON.parse(text);
    const content = json &&
      json.candidates &&
      json.candidates[0] &&
      json.candidates[0].content &&
      json.candidates[0].content.parts &&
      json.candidates[0].content.parts[0] &&
      json.candidates[0].content.parts[0].text;
    if (!content) {
      Logger.log('Gemini レスポンス構造エラー');
      return '（Geminiからのレスポンスが空です）';
    }
    Logger.log('Gemini 完了: ' + content.length + '文字');
    return content;
  } catch (e) {
    Logger.log('Gemini パースエラー: ' + e.message);
    return '（Gemini レスポンス解析エラー: ' + e.message + '）';
  }
}
