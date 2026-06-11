// main.gs - オーケストレーター（UrlFetchApp.fetchAll並列実行）

function runKansaiHousingIntelligence() {
  const config = getConfig();
  const timestamp = new Date().toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
  Logger.log('[' + timestamp + '] 関西住宅市場インテリジェンス 開始');

  try {
    // Phase 1: RSSフィード並列収集（fetchAll）
    Logger.log('Phase 1: RSS収集');
    const rssResults = fetchRssFeeds();

    // Phase 2: Gemini / Perplexity / Grok を並列実行（fetchAll）
    Logger.log('Phase 2: エージェント並列実行');
    const agentResults = runAgentsInParallel(config, rssResults);

    // Phase 3: Claude編集長による統合レポート生成（同期）
    Logger.log('Phase 3: Claude統合レポート生成');
    const finalReport = generateFinalReport(config, {
      gemini:     agentResults.gemini,
      perplexity: agentResults.perplexity,
      grok:       agentResults.grok,
      rss:        rssResults,
    });

    // Phase 4: Slack送信
    Logger.log('Phase 4: Slack送信');
    sendToSlack(finalReport, timestamp);

    Logger.log('[完了] ' + timestamp);
  } catch (e) {
    Logger.log('致命的エラー: ' + e.message + '\n' + e.stack);
    sendErrorToSlack(e.message);
    throw e;
  }
}

function runAgentsInParallel(config, rssResults) {
  const requests = [
    buildGeminiRequest(config, rssResults),
    buildPerplexityRequest(config),
    buildGrokRequest(config),
  ];

  Logger.log('fetchAll: ' + requests.length + '件のAPIリクエストを並列実行');

  let responses;
  try {
    responses = UrlFetchApp.fetchAll(requests);
  } catch (e) {
    Logger.log('fetchAll 失敗、順次実行にフォールバック: ' + e.message);
    responses = requests.map(function(req) {
      try {
        return UrlFetchApp.fetch(req.url, req);
      } catch (err) {
        // ダミーレスポンスを返してパーサーにエラー処理させる
        return {
          getResponseCode: function() { return 500; },
          getContentText:  function() { return JSON.stringify({ error: err.message }); },
        };
      }
    });
  }

  return {
    gemini:     parseGeminiResponse(responses[0]),
    perplexity: parsePerplexityResponse(responses[1]),
    grok:       parseGrokResponse(responses[2]),
  };
}

// ─── トリガー管理 ───────────────────────────────────────────

// 毎朝8時 JST に自動実行するトリガーを設定
function setDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('runKansaiHousingIntelligence')
    .timeBased()
    .everyDays(1)
    .atHour(8)
    .inTimezone('Asia/Tokyo')
    .create();
  Logger.log('毎日8:00 JST のトリガーを設定しました');
}

// 既存トリガーをすべて削除
function clearAllTriggers() {
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });
  Logger.log('すべてのトリガーを削除しました');
}

// 手動テスト実行
function runTest() {
  runKansaiHousingIntelligence();
}
