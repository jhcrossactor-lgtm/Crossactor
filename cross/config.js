// クロス 設定ファイル
// ここに秘密情報（APIキー等）は書かない。config.local.js（gitignore済）で上書き可能。
window.CROSS_CONFIG = {
  charaName: "クロス",
  brand: "Crossactor",

  // Supabase（公開可の値。config.local.js で上書き）
  supabaseUrl: "https://YOUR_PROJECT_REF.supabase.co",
  supabasePublishableKey: "",   // sb_publishable_... （legacy anon key も可）
  accessKey: "",                // 合言葉。Secrets に CROSS_ACCESS_KEY を設定した場合のみ

  // 会話
  // 表示用。実際の選択はサーバー側（Secrets の MODEL_UPPER / MODEL_MAX / UPPER_EFFORT / MAX_EFFORT で変更可）
  // default: 既定 ／ upper: キーワードで自動昇格 ／ max: チップで手動選択した時のみ
  models: {
    default: "claude-haiku-4-5-20251001",
    upper: "claude-sonnet-5",
    max: "claude-fable-5-1",
  },
  upgradeKeywords: ["分析", "事業", "計算", "比較"],
  wakeWord: "クロス",
  historyTurns: 10,          // 直近N往復を保持
  idleTimeoutMs: 20000,      // 無発話でidleへ戻るまで

  // 音声（Azure Speech）。enabled:false で音声なし（字幕のみ）
  voice: {
    enabled: true,
    name: "ja-JP-NanamiNeural",  // 女声。他: ja-JP-AoiNeural（若い）, ja-JP-MayuNeural（柔らかい）, 男声 ja-JP-KeitaNeural
    style: "chat",               // Nanami は chat / cheerful / customerservice が使える。非対応の声では無視される
    rate: "+6%",
    pitch: "+2%",
  },

  // 字幕（テロップ）
  subtitle: {
    scale: 1.0,        // 文字サイズ倍率（0.8〜1.5 目安）
    inputOpen: false,  // 起動時にテキスト入力欄を出すか（Tキーで切替）
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
