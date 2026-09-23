import Anthropic from '@anthropic-ai/sdk';
import { config } from './config.js';

// 拒否時はサーバー側で自動フォールバック（モデルリスト管理不要）
const FALLBACK = { betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default' };

const WRITER_SYSTEM = `あなたはnote向けの記事ライターだ。
- 日本語、Markdownで書く。1行目は「# タイトル」、以降が本文。
- 本文は2000〜3000字。見出しは ## と ### のみ使う。
- 数字・統計・固有の事例は、確かなもの以外は書かない。不確かな場合は一般論として書く。
- 実在の個人を特定できる情報（氏名・所属・住所・SNSアカウント等）は書かない。
- 誇大表現・断定しすぎる表現（「必ず」「絶対」「100%」等）は避ける。
- 記事本文以外（前置き・後書き・注釈）は出力しない。`;

const imageRule = (n) => n > 0 ? `
- 本文の理解を助ける差し込み画像を最大${n}か所、見出しの直後などに次の形式で単独行として入れる：
  <!-- image: 画像生成用の英語プロンプト（被写体・構図・雰囲気を具体的に） | alt: 日本語の画像説明 -->
  画像内に文字・ロゴ・実在人物を含めない前提でプロンプトを書く。` : '';

// ジャンル定義を記事生成・審査の指示に落とす
function genreBrief(ed, genre, forCheck = false) {
  const lines = [
    `【ジャンル】${genre.name}`,
    `想定読者の基本像: ${genre.reader}`,
    `切り口: ${genre.angle}`,
    `トーン: ${genre.tone}`,
    ...genre.rules.map((r) => `ルール: ${r}`),
  ];
  if (genre.paid?.enabled) {
    lines.push(forCheck
      ? '有料記事: <!-- paywall --> より前が無料部分。無料部分だけで記事の価値と結論の方向性が伝わるか、有料部分に対価に見合う具体性があるかも審査する。'
      : `有料記事: 無料部分（${genre.paid.freePart}）のあとに、単独行で <!-- paywall --> を1つだけ置き、その後に有料部分（${genre.paid.paidPart}）を書く。無料部分は全体の3〜4割。`);
  }
  if (genre.affiliate) {
    const list = ed.affiliates.map((a) => `- id=${a.id} / ${a.name} / ${a.category} / ${a.description}`).join('\n');
    lines.push(forCheck
      ? `アフィリエイト記事: 紹介内容が次の商品情報と矛盾していないか、情報にない特徴・料金・実績を書いていないか、効果を保証していないかを審査する。\n${list}`
      : `アフィリエイト記事: 次の商品から記事に合うものだけを選び、リンクを置く位置に単独行で <!-- affiliate: id --> を書く。URLは絶対に書かない。商品情報にない特徴・料金・実績は書かない。PR表記はシステムが付けるので書かない。\n${list}`);
  }
  return lines.join('\n');
}

const CHECK_SYSTEM = `あなたは公開前の記事を審査する編集者だ。次の3観点で記事を検査し、JSONで判定する。
1. fact: 出典なしの具体的数値・統計、誤りの可能性が高い事実、実在企業・製品についての未確認の主張
2. assertion: 読者に損害を与えうる断定（医療・法律・投資・効果保証など）、誇大表現
3. personal: 実在の個人を特定できる情報、第三者のプライバシー侵害
<!-- image: ... --> 行は差し込み画像の生成指示。実在人物・ロゴ・商標・他者の作風の模倣を求めるものは personal / fact として指摘する。
1件でも公開に不適切な問題があれば ok=false。軽微な表現の好みは ok=true のまま issues に書かない。`;

const CHECK_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          category: { type: 'string', enum: ['fact', 'assertion', 'personal'] },
          excerpt: { type: 'string' },
          reason: { type: 'string' },
        },
        required: ['category', 'excerpt', 'reason'],
        additionalProperties: false,
      },
    },
  },
  required: ['ok', 'issues'],
  additionalProperties: false,
};

function assertNotRefused(msg, step) {
  if (msg.stop_reason === 'refusal') throw new Error(`${step}: モデルが応答を拒否 (${msg.stop_details?.category ?? 'unknown'})`);
  if (msg.stop_reason === 'max_tokens') throw new Error(`${step}: 出力が上限で途切れた`);
}
const textOf = (msg) => msg.content.filter((b) => b.type === 'text').map((b) => b.text).join('');

export function splitTitle(markdown) {
  const lines = markdown.trim().split('\n');
  const m = lines[0].match(/^#\s+(.+)$/);
  if (!m) throw new Error('生成記事の1行目がタイトル（# ...）になっていない');
  return { title: m[1].trim(), body: lines.slice(1).join('\n').trim() };
}

export async function generateArticle(topic, ed, genre) {
  if (config.mockLlm) return mockArticle(topic, genre);
  const client = new Anthropic();
  const stream = client.beta.messages.stream({
    model: config.model,
    max_tokens: 64000,
    thinking: { type: 'adaptive' },
    ...FALLBACK,
    system: `${WRITER_SYSTEM}${imageRule(config.imageCount)}\n\n${genreBrief(ed, genre)}`,
    messages: [{
      role: 'user',
      content: `テーマ: ${topic.theme}\n想定読者: ${topic.reader}\n伝えたいこと: ${topic.message}\n\nこの条件で記事を書いてください。`,
    }],
  });
  const msg = await stream.finalMessage();
  assertNotRefused(msg, '記事生成');
  return splitTitle(textOf(msg));
}

export async function checkArticle({ title, body }, ed, genre) {
  if (config.mockLlm) return { ok: process.env.NOTE_POST_MOCK_CHECK !== 'ng', issues: [] };
  const client = new Anthropic();
  const msg = await client.beta.messages.create({
    model: config.model,
    max_tokens: 16000,
    thinking: { type: 'adaptive' },
    ...FALLBACK,
    output_config: { format: { type: 'json_schema', schema: CHECK_SCHEMA } },
    system: `${CHECK_SYSTEM}\n\n${genreBrief(ed, genre, true)}`,
    messages: [{ role: 'user', content: `<article>\n# ${title}\n\n${body}\n</article>` }],
  });
  assertNotRefused(msg, '自己チェック');
  return JSON.parse(textOf(msg));
}

function mockArticle(topic, genre) {
  const para = `${topic.message}。これは動作確認用のダミー本文だ。`.repeat(20);
  const wall = genre.paid?.enabled ? '<!-- paywall -->\n\n' : '';
  const aff = genre.affiliate ? `<!-- affiliate: ${process.env.NOTE_POST_MOCK_AFF || 'svc1'} -->\n\n` : '';
  const url = process.env.NOTE_POST_MOCK_URL ? `詳しくは ${process.env.NOTE_POST_MOCK_URL} を参照。\n\n` : '';
  return {
    title: `【テスト】${topic.theme}`,
    body: `## はじめに\n\n${para}\n\n## ポイント\n\n- 項目1\n- 項目2\n\n<!-- image: A small office team using laptops, warm light | alt: AIを使う小さなオフィス -->\n\n**太字**のテスト。\n\n${wall}${aff}${url}## まとめ\n\n${para}`,
  };
}

// ---- テーマ提案 ----

const PROPOSE_SCHEMA = {
  type: 'object',
  properties: {
    topics: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          genre: { type: 'string' },
          theme: { type: 'string' },
          reader: { type: 'string' },
          message: { type: 'string' },
          tags: { type: 'string' },
          reason: { type: 'string' },
        },
        required: ['genre', 'theme', 'reader', 'message', 'tags', 'reason'],
        additionalProperties: false,
      },
    },
  },
  required: ['topics'],
  additionalProperties: false,
};

/**
 * ジャンルごとに記事テーマ案を出す。既存テーマ（done）と重複させない。
 * 戻り値: [{genre, theme, reader, message, tags, reason}]
 */
export async function proposeTopics(ed, genres, perGenre, done) {
  if (config.mockLlm) {
    return genres.flatMap((g) => Array.from({ length: perGenre }, (_, k) => ({
      genre: g.id, theme: `${g.name}の案${k + 1}-${Date.now() % 100000}`, reader: g.reader, message: '要点', tags: 'タグ1;タグ2', reason: 'モック',
    })));
  }
  const brief = genres.map((g) => `${genreBrief(ed, g)}\nジャンルID: ${g.id}`).join('\n\n');
  const client = new Anthropic();
  const msg = await client.beta.messages.create({
    model: config.model,
    max_tokens: 16000,
    thinking: { type: 'adaptive' },
    ...FALLBACK,
    output_config: { format: { type: 'json_schema', schema: PROPOSE_SCHEMA } },
    system: `あなたはnoteの編集長だ。ジャンル定義に沿って、読者が読みたくなり、かつ事実誤認のリスクが低い記事テーマを提案する。
- 各ジャンル${perGenre}件ずつ。genre にはジャンルIDを入れる
- theme は記事の主題（30字程度）、reader は具体的な読者像、message は記事で伝える一番のこと、tags は ; 区切りで3〜5個、reason は提案理由（1文）
- 既出テーマと主題が重なるものは出さない`,
    messages: [{ role: 'user', content: `${brief}\n\n【既出テーマ】\n${done.map((t) => `- ${t}`).join('\n') || '(なし)'}` }],
  });
  assertNotRefused(msg, 'テーマ提案');
  const ids = new Set(genres.map((g) => g.id));
  return JSON.parse(textOf(msg)).topics.filter((t) => ids.has(t.genre));
}
