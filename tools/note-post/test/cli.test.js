import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { startFakeNote } from './fake-note.js';

const CLI = path.resolve(import.meta.dirname, '../src/cli.js');
const CHROMIUM = process.env.NOTE_CHROMIUM_PATH || undefined;
let fake, dir;

before(async () => { fake = await startFakeNote(); });
after(() => fake.server.close());

function sandbox() {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'note-post-'));
  fs.writeFileSync(path.join(dir, 'topics.csv'),
    'theme,reader,message,tags,status\n"テーマA, カンマ入り",経営者,伝えたいこと,AI;中小企業,\nテーマB,読者,msg,x,\n');
  return {
    ...process.env,
    NOTE_BASE_URL: fake.base,
    NOTE_POST_MOCK_LLM: '1',
    NOTE_STATE_PATH: path.join(dir, 'state.json'),
    NOTE_TOPICS_PATH: path.join(dir, 'topics.csv'),
    NOTE_POSTED_PATH: path.join(dir, 'posted.csv'),
    NOTE_STOP_PATH: path.join(dir, 'STOP'),
    NOTE_OUT_DIR: path.join(dir, 'out'),
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
  assert.match(posted(env), /dry_run/);
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /中小企業,\n/); // status空のまま
  // dry-runは1日1本の枠を消費しない
  assert.equal((await run(env, 'run', '--dry-run')).status, 0);
  assert.equal(posted(env).match(/dry_run/g).length, 2);
});

test('本番run: 公開→URL記録、2回目は1日1本制限で終了', async () => {
  const env = await loggedIn(sandbox());
  const before = fake.state.published.length;
  let r = await run(env, 'run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(fake.state.published.length, before + 1);
  assert.deepEqual(fake.state.published.at(-1).tags, ['AI', '中小企業']);
  assert.match(posted(env), /published,"テーマA, カンマ入り",.*\/n\/n123/);
  assert.match(fs.readFileSync(env.NOTE_TOPICS_PATH, 'utf8'), /中小企業,published/);
  r = await run(env, 'run');
  assert.match(r.stdout, /1日1本制限/);
  assert.equal(fake.state.published.length, before + 1);
});

test('自己チェックNG → 下書きのみ、status=draft_ng', async () => {
  const env = await loggedIn(sandbox());
  const before = fake.state.published.length;
  const r = await run({ ...env, NOTE_POST_MOCK_CHECK: 'ng' }, 'run');
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.equal(fake.state.published.length, before);
  assert.match(posted(env), /draft_ng/);
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
