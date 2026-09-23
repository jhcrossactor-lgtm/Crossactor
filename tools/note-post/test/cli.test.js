import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { startFakeNote } from './fake-note.js';
import { readTable, writeTable } from '../src/csv.js';

const CLI = path.resolve(import.meta.dirname, '../src/cli.js');
const CHROMIUM = process.env.NOTE_CHROMIUM_PATH || undefined;
let fake, dir;

before(async () => { fake = await startFakeNote(); });
after(() => fake.server.close());

function sandbox(opts = {}) {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'note-post-'));
  fs.writeFileSync(path.join(dir, 'topics.csv'),
    'genre,theme,reader,message,tags,status\nai-smb,"テーマA, カンマ入り",経営者,伝えたいこと,AI;中小企業,\naffiliate,テーマB,読者,msg,x,\n');
  // 価格を決めたジャンル定義（本物は price=null で決定待ち）
  const g = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../genres.json'), 'utf8'));
  for (const x of g.genres) if (x.paid?.enabled) x.paid.price = opts.price === undefined ? 500 : opts.price;
  fs.writeFileSync(path.join(dir, 'genres.json'), JSON.stringify(g));
  fs.writeFileSync(path.join(dir, 'affiliates.csv'), opts.affiliates ?? 'id,name,url,category,description\nsvc1,テストサービス,https://px.example.com/svc1,スクール,オンライン講座\n');
  return {
    ...process.env,
    NOTE_BASE_URL: fake.base,
    NOTE_POST_MOCK_LLM: '1',
    NOTE_STATE_PATH: path.join(dir, 'state.json'),
    NOTE_TOPICS_PATH: path.join(dir, 'topics.csv'),
    NOTE_POSTED_PATH: path.join(dir, 'posted.csv'),
    NOTE_STOP_PATH: path.join(dir, 'STOP'),
    NOTE_OUT_DIR: path.join(dir, 'out'),
    NOTE_GENRES_PATH: path.join(dir, 'genres.json'),
    NOTE_AFFILIATES_PATH: path.join(dir, 'affiliates.csv'),
    NOTE_PROPOSALS_PATH: path.join(dir, 'proposals.csv'),
    SLACK_WEBHOOK_URL: '',
    ...(CHROMIUM ? { NOTE_CHROMIUM_PATH: CHROMIUM } : {}),
  };
}
// 非同期spawn必須（同期だとダミーサーバーのイベントループが止まる）
const run = (env, ...args) => new Promise((resolve) => {
  const p = spawn('node', [CLI, ...args], { env });
  let stdout = '', stderr = '';
  p.stdout.on('data', (d) => (stdout += d));
  p.stderr.on('data', (d) => (stderr += d));
  p.stdin.end('\n');
  p.on('close', (status) => resolve({ status, stdout, stderr }));
});
const posted = (env) => fs.existsSync(env.NOTE_POSTED_PATH) ? fs.readFileSync(env.NOTE_POSTED_PATH, 'utf8') : '';

async function loggedIn(env) {
  // login はヘッドありブラウザを使う。CIでは xvfb-run 経由で実行する
  const r = await run(env, 'login');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.ok(fs.existsSync(env.NOTE_STATE_PATH));
  assert.equal(fs.statSync(env.NOTE_STATE_PATH).mode & 0o777, 0o600);
  return env;
}

test('login → storageState保存、dry-runで下書き保存のみ・トピックは未処理のまま', async () => {
  const env = await loggedIn(sandbox());
  const r = await run(env, 'run', '--dry-run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(fake.state.published.length, 0);
  const d = fake.state.drafts.at(-1);
  assert.match(d.title, /テーマA, カンマ入り/);
  assert.match(d.html, /<h2>はじめに<\/h2>/);
  assert.match(d.html, /<strong>太字<\/strong>/);
  // 画像はマーカー位置（リストの後・太字の前）に差し込まれ、マーカー文字列は残らない
  assert.match(d.html, /<\/ul>[\s\S]*<img data-name="[^"]+-img1\.png"[\s\S]*<strong>太字/);
  assert.doesNotMatch(d.html, /image:/);
  const md = fs.readFileSync(path.join(env.NOTE_OUT_DIR, fs.readdirSync(env.NOTE_OUT_DIR).find((f) => f.endsWith('.md'))), 'utf8');
  assert.match(md, /!\[AIを使う小さなオフィス\]\(.+-img1\.png\)/);
  assert.match(posted(env), /dry_run/);
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /中小企業,\n/); // status空のまま
  // dry-runは1日1本の枠を消費しない
  assert.equal((await run(env, 'run', '--dry-run')).status, 0);
  assert.equal(posted(env).match(/dry_run/g).length, 2);
});

const rows = (env) => readTable(env.NOTE_POSTED_PATH).rows;
const draftIdx = (row) => Number(row.draft_url.match(/\/notes\/n(\d+)\/edit/)[1]);

test('run は公開せず在庫に積む。同日2回目は1日1本で終了、翌日は在庫が残っていても新規作成', async () => {
  const env = await loggedIn(sandbox());
  const pubBefore = fake.state.published.length;
  let r = await run(env, 'run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(fake.state.published.length, pubBefore);
  assert.deepEqual(rows(env).map((x) => [x.id, x.status]), [['1', 'pending']]);
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /中小企業,pending/);
  assert.match(r.stderr, /在庫追加 #1 \[小さな会社のAI活用・有料\]（自己チェックOK）[\s\S]*確認待ち在庫: 1本/);

  r = await run(env, 'run');
  assert.match(r.stdout, /1日1本制限/);

  // 日付を前日にずらして翌日の run を再現
  const t = readTable(env.NOTE_POSTED_PATH);
  t.rows[0].date = '2000-01-01';
  writeTable(env.NOTE_POSTED_PATH, t.header, t.rows);
  r = await run(env, 'run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.deepEqual(rows(env).map((x) => [x.id, x.status, x.theme]), [['1', 'pending', 'テーマA, カンマ入り'], ['2', 'pending', 'テーマB']]);
  assert.match(r.stderr, /確認待ち在庫: 2本/);

  r = await run(env, 'list');
  assert.match(r.stdout, /在庫 2本[\s\S]*#1[\s\S]*#2/);
});

test('publish <番号>: 選んだ在庫を note上の手直しごと公開、1日1本', async () => {
  const env = await loggedIn(sandbox());
  await run(env, 'run');
  const t = readTable(env.NOTE_POSTED_PATH);
  t.rows[0].date = '2000-01-01';
  writeTable(env.NOTE_POSTED_PATH, t.header, t.rows);
  await run(env, 'run');

  // 番号なし・存在しない番号は一覧を出して拒否
  let r = await run(env, 'publish');
  assert.equal(r.status, 1);
  assert.match(r.stdout, /在庫 2本/);
  assert.equal((await run(env, 'publish', '99')).status, 1);

  // #2 をnote上で手直ししてから公開
  const target = rows(env).find((x) => x.id === '2');
  fake.state.drafts[draftIdx(target)].html += '<p>ほせもやん加筆</p>';
  r = await run(env, 'publish', '2');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  const pub = fake.state.published.at(-1);
  assert.match(pub.html, /ほせもやん加筆/);
  assert.deepEqual(pub.tags, ['x']);
  const done = rows(env).find((x) => x.id === '2');
  assert.equal(done.status, 'published');
  assert.match(done.url, /\/n\/n\d+$/);
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /affiliate,テーマB,読者,msg,x,published/);
  assert.equal(pub.paid, false); // アフィリエイトは無料
  assert.equal(rows(env).find((x) => x.id === '1').status, 'pending');

  r = await run(env, 'publish', '1');
  assert.match(r.stdout, /1日1本制限/);
  assert.equal(rows(env).find((x) => x.id === '1').status, 'pending');
});

test('自己チェックNG → 在庫(pending_ng)、--force なしでは公開不可、reject で見送り', async () => {
  const env = await loggedIn(sandbox());
  let r = await run({ ...env, NOTE_POST_MOCK_CHECK: 'ng' }, 'run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(rows(env)[0].status, 'pending_ng');
  assert.match(r.stderr, /⚠自己チェックNG/);
  // NG記事には画像を作らず、マーカーも本文に残さない
  assert.ok(!fs.readdirSync(env.NOTE_OUT_DIR).some((f) => f.endsWith('.png')));
  assert.doesNotMatch(fake.state.drafts.at(-1).html, /image:|<img/);

  const pubBefore = fake.state.published.length;
  r = await run(env, 'publish', '1');
  assert.equal(r.status, 1);
  assert.match(r.stderr, /--force/);
  assert.equal(fake.state.published.length, pubBefore);

  r = await run(env, 'reject', '1');
  assert.equal(r.status, 0);
  assert.equal(rows(env)[0].status, 'rejected');
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /中小企業,rejected/);
});

test('NG在庫も --force で公開できる', async () => {
  const env = await loggedIn(sandbox());
  await run({ ...env, NOTE_POST_MOCK_CHECK: 'ng' }, 'run');
  const r = await run(env, 'publish', '1', '--force');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(rows(env)[0].status, 'published');
});

test('ジャンルをローテーション。有料ジャンルは区切りの直後に有料ライン＋価格を設定して公開', async () => {
  const env = await loggedIn(sandbox());
  await run(env, 'run');
  const t = readTable(env.NOTE_POSTED_PATH);
  t.rows[0].date = '2000-01-01';
  writeTable(env.NOTE_POSTED_PATH, t.header, t.rows);
  await run(env, 'run');
  assert.deepEqual(rows(env).map((x) => [x.genre, x.paid]), [['ai-smb', '1'], ['affiliate', '']]);

  // 有料記事: 本文に区切り文言、公開時に価格と有料ライン
  const paidDraft = fake.state.drafts[draftIdx(rows(env)[0])];
  assert.match(paidDraft.html, /ここから有料/);
  let r = await run(env, 'publish', '1');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  const pub = fake.state.published.at(-1);
  assert.equal(pub.paid, true);
  assert.equal(pub.price, '500');
  assert.match(pub.paywallAfter, /ここから有料/);

  // アフィリエイト記事: IDがリストのリンクに展開され、先頭にPR表記
  const affDraft = fake.state.drafts[draftIdx(rows(env)[1])];
  assert.match(affDraft.html, /アフィリエイト広告（PR）を含みます/);
  assert.match(affDraft.html, /<a href="https:\/\/px\.example\.com\/svc1">テストサービス（PR）<\/a>/);
  assert.doesNotMatch(affDraft.html, /affiliate:|paywall/);
});

test('価格未設定の有料記事は publish できない', async () => {
  const env = await loggedIn(sandbox({ price: null }));
  await run(env, 'run');
  const before = fake.state.published.length;
  const r = await run(env, 'publish', '1');
  assert.equal(r.status, 1);
  assert.match(r.stderr, /ai-smb\.paid\.price/);
  assert.equal(fake.state.published.length, before);
});

test('ルール違反（AIが書いたURL・リストにない商品ID）は NG 在庫になる', async () => {
  let env = await loggedIn(sandbox());
  await run({ ...env, NOTE_POST_MOCK_URL: 'https://evil.example.com/x' }, 'run');
  assert.equal(rows(env)[0].status, 'pending_ng');
  assert.match(rows(env)[0].issues, /\[rule\]https:\/\/evil/);

  // アフィリエイトジャンルだけ残して存在しないIDを使わせる
  env = await loggedIn(sandbox());
  const tp = readTable(env.NOTE_TOPICS_PATH);
  tp.rows[0].status = 'skip';
  writeTable(env.NOTE_TOPICS_PATH, tp.header, tp.rows);
  await run({ ...env, NOTE_POST_MOCK_AFF: 'nope' }, 'run');
  assert.equal(rows(env)[0].genre, 'affiliate');
  assert.equal(rows(env)[0].status, 'pending_ng');
  assert.match(rows(env)[0].issues, /affiliates\.csv にないID: nope/);
});

test('商品リストが空ならアフィリエイトジャンルは飛ばす', async () => {
  const env = await loggedIn(sandbox({ affiliates: 'id,name,url,category,description\n' }));
  const tp = readTable(env.NOTE_TOPICS_PATH);
  tp.rows[0].status = 'skip';
  writeTable(env.NOTE_TOPICS_PATH, tp.header, tp.rows);
  const r = await run(env, 'run');
  assert.match(r.stdout, /書ける未処理テーマがない/);
  assert.equal(rows(env).length, 0);
});

test('テーマが減ったらAIが提案 → accept したものだけ topics.csv に入る', async () => {
  const env = await loggedIn(sandbox());
  const r = await run(env, 'run');
  assert.match(r.stderr, /テーマ案 \d+件/);
  const open = readTable(env.NOTE_PROPOSALS_PATH).rows;
  assert.ok(open.length >= 3 && open.every((x) => x.status === 'open'));
  // 未回答があるうちは追加提案しない
  const t = readTable(env.NOTE_POSTED_PATH);
  t.rows[0].date = '2000-01-01';
  writeTable(env.NOTE_POSTED_PATH, t.header, t.rows);
  await run(env, 'run');
  assert.equal(readTable(env.NOTE_PROPOSALS_PATH).rows.length, open.length);

  assert.equal((await run(env, 'accept', '1', '2')).status, 0);
  assert.equal((await run(env, 'decline', '3')).status, 0);
  const st = readTable(env.NOTE_PROPOSALS_PATH).rows.map((x) => x.status);
  assert.deepEqual(st.slice(0, 3), ['accepted', 'accepted', 'declined']);
  const topicsNow = readTable(env.NOTE_TOPICS_PATH).rows;
  assert.ok(topicsNow.some((x) => x.theme === open[0].theme && x.genre === open[0].genre && x.status === ''));
  assert.ok(!topicsNow.some((x) => x.theme === open[2].theme));
});

test('NOTE_IMAGE_COUNT=0 なら画像なしで下書き保存', async () => {
  const env = await loggedIn(sandbox());
  const r = await run({ ...env, NOTE_IMAGE_COUNT: '0' }, 'run', '--dry-run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.doesNotMatch(fake.state.drafts.at(-1).html, /image:|<img/);
});

test('STOPファイルがあれば何もせず終了', async () => {
  const env = sandbox();
  fs.writeFileSync(env.NOTE_STOP_PATH, '');
  const r = await run(env, 'run', '--dry-run');
  assert.equal(r.status, 0);
  assert.match(r.stdout, /STOPファイル検出/);
  assert.equal(posted(env), '');
});

test('ログイン切れ → exit 2（Slack通知経路）', async () => {
  const env = sandbox();
  fs.writeFileSync(env.NOTE_STATE_PATH, JSON.stringify({ cookies: [], origins: [] }));
  fake.state.autoLogin = false;
  const r = await run(env, 'run', '--dry-run').finally(() => (fake.state.autoLogin = true));
  assert.equal(r.status, 2);
  assert.match(r.stderr, /ログイン切れ/);
  assert.match(r.stderr, /SLACK_WEBHOOK_URL未設定のため通知スキップ/);
});

test('セレクタ不一致 → exit 2、スクショ保存', async () => {
  const env = await loggedIn(sandbox());
  const sel = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../selectors.json'), 'utf8'));
  sel.editor.title = "textarea[placeholder='存在しない']";
  const selPath = path.join(dir, 'selectors.json');
  fs.writeFileSync(selPath, JSON.stringify(sel));
  const r = await run({ ...env, NOTE_SELECTORS_PATH: selPath }, 'run', '--dry-run');
  assert.equal(r.status, 2);
  assert.match(r.stderr, /セレクタ不一致: editor.title/);
  assert.ok(fs.readdirSync(env.NOTE_OUT_DIR).some((f) => f.startsWith('error-')));
});
