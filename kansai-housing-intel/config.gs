// config.gs - APIキー・設定値管理（PropertiesService使用）

function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    // APIキー
    GEMINI_API_KEY:      props.getProperty('GEMINI_API_KEY')      || '',
    CLAUDE_API_KEY:      props.getProperty('CLAUDE_API_KEY')      || '',
    PERPLEXITY_API_KEY:  props.getProperty('PERPLEXITY_API_KEY')  || '',
    GROK_API_KEY:        props.getProperty('GROK_API_KEY')        || '',
    SLACK_WEBHOOK_URL:   props.getProperty('SLACK_WEBHOOK_URL')   || '',

    // モデル設定
    GEMINI_MODEL:      'gemini-2.5-flash',
    CLAUDE_MODEL:      'claude-sonnet-4-6',
    PERPLEXITY_MODEL:  'sonar',
    GROK_MODEL:        'grok-2-latest',

    // IR監視対象企業
    TARGET_COMPANIES: [
      '飯田グループHD',
      'ケイアイスター不動産',
      '住友林業',
      '積水ハウス',
      'オープンハウスグループ',
    ],

    // 対象エリア
    TARGET_AREAS: ['大阪', '兵庫', '京都', '滋賀', '奈良', '和歌山'],

    // APIエンドポイント
    GEMINI_ENDPOINT:      'https://generativelanguage.googleapis.com/v1beta/models/',
    CLAUDE_ENDPOINT:      'https://api.anthropic.com/v1/messages',
    PERPLEXITY_ENDPOINT:  'https://api.perplexity.ai/chat/completions',
    GROK_ENDPOINT:        'https://api.x.ai/v1/chat/completions',
  };
}

// 初回セットアップ用：値を書き換えてから実行する
function setupProperties() {
  const props = PropertiesService.getScriptProperties();
  props.setProperties({
    GEMINI_API_KEY:     'YOUR_GEMINI_API_KEY',
    CLAUDE_API_KEY:     'YOUR_CLAUDE_API_KEY',
    PERPLEXITY_API_KEY: 'YOUR_PERPLEXITY_API_KEY',
    GROK_API_KEY:       'YOUR_GROK_API_KEY',
    SLACK_WEBHOOK_URL:  'YOUR_SLACK_INCOMING_WEBHOOK_URL',
  });
  Logger.log('PropertiesService にキーを保存しました');
}

// 設定確認用（値はマスク表示）
function checkProperties() {
  const config = getConfig();
  const keys = ['GEMINI_API_KEY', 'CLAUDE_API_KEY', 'PERPLEXITY_API_KEY', 'GROK_API_KEY', 'SLACK_WEBHOOK_URL'];
  keys.forEach(k => {
    const val = config[k];
    const masked = val ? val.substring(0, 6) + '...' : '（未設定）';
    Logger.log(`${k}: ${masked}`);
  });
}
