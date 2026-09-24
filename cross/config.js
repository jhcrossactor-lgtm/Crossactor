// クロス 設定ファイル
// ここに秘密情報（APIキー等）は書かない。config.local.js（gitignore済）で上書き可能。
window.CROSS_CONFIG = {
  charaName: "クロス",
  brand: "Crossactor",

  // Supabase（公開可の値。config.local.js で上書き）
  supabaseUrl: "https://YOUR_PROJECT_REF.supabase.co",
  supabaseAnonKey: "",

  // 会話
  models: {
    default: "claude-haiku-4-5-20251001",
    upper: "claude-sonnet-5",
  },
  upgradeKeywords: ["分析", "事業", "計算", "比較"],
  wakeWord: "クロス",
  historyTurns: 10,          // 直近N往復を保持
  idleTimeoutMs: 20000,      // 無発話でidleへ戻るまで

  // 音声（Step②で使用）
  voice: {
    name: "ja-JP-KeitaNeural",
    style: "chat",
    rate: "+5%",
    pitch: "-2%",
  },

  // 色
  colors: {
    bg: "#0b0713",
    accent: "#a855f7",
    user: "#7dd3fc",
    ai: "#f9a8d4",
    error: "#f87171",
  },
};
