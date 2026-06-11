// agent_claude.gs - Claude（編集長・最終レポート統合担当）

function generateFinalReport(config, allData) {
  const rssText = formatRssForReport(allData.rss);
  const today = new Date().toLocaleDateString('ja-JP', { timeZone: 'Asia/Tokyo' });

  const systemPrompt =
    'あなたは関西圏の住宅・不動産市場に精通したエコノミスト兼編集長です。\n' +
    '複数のAIエージェントが収集・分析したデータを統合し、\n' +
    '投資家・事業者・政策担当者が即座に活用できる高品質なインテリジェンスレポートを作成してください。\n\n' +
    '【レポート作成の原則】\n' +
    '1. 事実と分析を明確に区別する\n' +
    '2. 数値・情報源を可能な限り明記する\n' +
    '3. アクションにつながる示唆を含める\n' +
    '4. 冗長な表現を避け情報密度を高める\n' +
    '5. 関西圏全体のトレンドと各府県の差異を意識する';

  const userPrompt =
    '以下のデータを統合して、' + today + '付けの関西住宅市場インテリジェンスレポートを作成してください。\n\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n' +
    '【Gemini分析（マクロ・定量）】\n' +
    (allData.gemini || '（取得なし）') + '\n\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n' +
    '【Perplexity（最新WEB・IR情報）】\n' +
    (allData.perplexity || '（取得なし）') + '\n\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n' +
    '【Grok（X/SNSリアルタイム）】\n' +
    (allData.grok || '（取得なし）') + '\n\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n' +
    '【RSSニュース】\n' +
    rssText + '\n' +
    '━━━━━━━━━━━━━━━━━━━━━━\n\n' +
    '以下の5カテゴリ形式で、必ずJSON形式のみで返答してください（前後の説明文不要）：\n\n' +
    '{\n' +
    '  "macro": "① マクロ市況の内容（e-Stat着工統計・金利・コスト動向中心）",\n' +
    '  "corporate": "② 企業戦略の内容（IR・決算・用地取得・新プロジェクト中心）",\n' +
    '  "sales": "③ 実売データの内容（分譲価格・成約件数・住宅産業系メディア情報）",\n' +
    '  "leading": "④ 先行指標の内容（用地取得・建築確認・住宅産業新聞の先行記事）",\n' +
    '  "field": "⑤ 現場の生の声（X/SNSセンチメント・RSSニュースの現場感）",\n' +
    '  "summary": "全体サマリー（3行以内。今週の最重要インサイト）"\n' +
    '}\n\n' +
    '各カテゴリの内容は200〜400字。箇条書きを活用し、数値・出典を積極的に記載してください。';

  const body = {
    model: config.CLAUDE_MODEL,
    max_tokens: 4096,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  };

  const options = {
    method: 'POST',
    contentType: 'application/json',
    headers: {
      'x-api-key': config.CLAUDE_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  };

  let response;
  try {
    response = UrlFetchApp.fetch(config.CLAUDE_ENDPOINT, options);
  } catch (e) {
    Logger.log('Claude API呼び出しエラー: ' + e.message);
    return buildFallbackReport(allData);
  }

  return parseClaudeResponse(response, allData);
}

function parseClaudeResponse(response, allData) {
  try {
    const code = response.getResponseCode();
    const text = response.getContentText();
    if (code !== 200) {
      Logger.log('Claude エラー (' + code + '): ' + text.substring(0, 300));
      return buildFallbackReport(allData);
    }
    const json = JSON.parse(text);
    const content =
      json && json.content && json.content[0] && json.content[0].text;
    if (!content) {
      Logger.log('Claude レスポンス構造エラー');
      return buildFallbackReport(allData);
    }

    // JSONブロックを抽出（コードフェンス対応）
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      Logger.log('Claude レスポンスからJSONを抽出できませんでした');
      return {
        macro:     allData.gemini     || '（データなし）',
        corporate: allData.perplexity || '（データなし）',
        sales:     '（Claude統合エラー）',
        leading:   '（Claude統合エラー）',
        field:     allData.grok       || '（データなし）',
        summary:   content.substring(0, 300),
      };
    }

    const report = JSON.parse(jsonMatch[0]);
    Logger.log('Claude 統合レポート生成完了');
    return report;
  } catch (e) {
    Logger.log('Claude パースエラー: ' + e.message);
    return buildFallbackReport(allData);
  }
}

function buildFallbackReport(allData) {
  return {
    macro:     allData.gemini     || '（Geminiデータ取得エラー）',
    corporate: allData.perplexity || '（Perplexityデータ取得エラー）',
    sales:     '（データ取得エラーのため表示不可）',
    leading:   '（データ取得エラーのため表示不可）',
    field:     allData.grok       || '（Grokデータ取得エラー）',
    summary:   'データ収集に一部エラーが発生しました。各APIキーの設定を確認してください（setupProperties()を実行）。',
  };
}
