#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { config, todayJst } from './config.js';
import { readTable, writeTable, appendRow } from './csv.js';
import { generateArticle, checkArticle } from './llm.js';
import { login, saveDraft, publishDraft, LoginExpiredError, SelectorError } from './note.js';
import { notifySlack } from './slack.js';
import { generateImages, stripImageMarkers } from './images.js';

const POSTED_HEADER = ['id', 'date', 'status', 'theme', 'title', 'tags', 'draft_url', 'url', 'issues', 'published_at'];
// 確認待ち: pending（チェックOK）/ pending_ng（チェックNG）
const isPending = (r) => r.status === 'pending' || r.status === 'pending_ng';
const log = (...a) => console.log(`[note-post ${new Date().toISOString()}]`, ...a);

function stopIfRequested() {
  if (fs.existsSync(config.stopPath)) {
    log(`STOPファイル検出（${config.stopPath}）→ 終了`);
    process.exit(0);
  }
}

async function run({ dryRun }) {
  stopIfRequested();

  const today = todayJst();
  if (!dryRun) {
    const posted = readTable(config.postedPath).rows;
    const done = posted.filter((r) => r.date === today && r.status !== 'dry_run');
    if (done.length) {
      log(`本日（${today}）は作成済み（${done[0].status}）→ 1日1本制限で終了`);
      return;
    }
  }

  const topics = readTable(config.topicsPath);
  if (!topics.header.includes('status')) topics.header.push('status');
  const idx = topics.rows.findIndex((r) => !r.status?.trim());
  if (idx < 0) {
    log('未処理のトピックがない → 終了');
    return;
  }
  const topic = topics.rows[idx];
  const tags = (topic.tags || '').split(/[;；、]/).map((t) => t.trim().replace(/^#/, '')).filter(Boolean);
  log(`対象: ${topic.theme}${dryRun ? '（dry-run: 公開しない）' : ''}`);

  const article = await generateArticle(topic);
  log(`生成完了: 「${article.title}」 本文${article.body.length}字`);
  if (article.body.length < 1500 || article.body.length > 4000) log(`警告: 本文字数が想定外（${article.body.length}字）`);

  const check = await checkArticle(article);
  log(`自己チェック: ${check.ok ? 'OK' : 'NG'}${check.issues.length ? ` 指摘${check.issues.length}件` : ''}`);
  for (const i of check.issues) log(`  - [${i.category}] ${i.excerpt} … ${i.reason}`);

  fs.mkdirSync(config.outDir, { recursive: true });
  const base = path.join(config.outDir, `${today}-${idx + 1}${dryRun ? '-dry' : ''}`);

  stopIfRequested();

  // 自己チェック通過後にだけ画像を作る（NG記事に画像費用をかけない）
  let images = [];
  if (check.ok || dryRun) {
    const r = await generateImages(article.body, base);
    article.body = r.body;
    images = r.images;
    log(`画像: ${images.length}枚生成`);
    for (const e of r.errors) log(`  警告: ${e}`);
    if (r.errors.length && !dryRun) await notifySlack(`画像の一部を省略: ${r.errors.join(' / ')}`);
  } else {
    article.body = stripImageMarkers(article.body);
  }
  const localMd = images.reduce((md, im) => md.replace(im.marker, `![${im.alt}](${path.basename(im.file)})`), article.body);
  fs.writeFileSync(`${base}.md`, `# ${article.title}\n\n${localMd}\n`);
  fs.writeFileSync(`${base}.check.json`, JSON.stringify(check, null, 2));
  log(`ローカル保存: ${base}.md`);

  stopIfRequested();

  // 公開はしない。人の確認を経て publish コマンドで公開する
  const draftUrl = await saveDraft({ ...article, images });
  const status = dryRun ? 'dry_run' : check.ok ? 'pending' : 'pending_ng';
  log(`下書き保存（${status}）: ${draftUrl}`);

  const issues = check.issues.map((i) => `[${i.category}]${i.excerpt}: ${i.reason}`);
  const prev = readTable(config.postedPath).rows;
  const id = String(Math.max(0, ...prev.map((r) => Number(r.id) || 0)) + 1);
  appendRow(config.postedPath, POSTED_HEADER, {
    id, date: today, status, theme: topic.theme, title: article.title, tags: tags.join(';'),
    draft_url: draftUrl, url: '', issues: issues.join(' / '), published_at: '',
  });
  if (dryRun) return;

  topic.status = 'pending';
  writeTable(config.topicsPath, topics.header, topics.rows);
  const stock = prev.filter(isPending).length + 1;
  const head = check.ok
    ? `在庫追加 #${id}（自己チェックOK）`
    : `在庫追加 #${id}（⚠自己チェックNG ${issues.length}件）\n${issues.map((i) => `・${i}`).join('\n')}\n公開するなら \`note-post publish ${id} --force\``;
  await notifySlack(`${head}\n「${article.title}」\n${draftUrl}\n確認待ち在庫: ${stock}本。一覧は \`note-post list\`、公開は \`note-post publish <番号>\``);
}

function listStock() {
  const stock = readTable(config.postedPath).rows.filter(isPending);
  if (!stock.length) return log('確認待ちの在庫はない');
  console.log(`確認待ち在庫 ${stock.length}本（公開: note-post publish <番号>）`);
  for (const r of stock) {
    console.log(`#${r.id}  ${r.date}  ${r.status === 'pending_ng' ? '⚠NG ' : ''}「${r.title}」\n     ${r.draft_url}${r.issues ? `\n     指摘: ${r.issues}` : ''}`);
  }
}

// 番号指定で在庫から1本取り出す。未指定・該当なしは一覧を出して終了
function takeFromStock(id) {
  const posted = readTable(config.postedPath);
  const row = id && posted.rows.find((r) => r.id === id && isPending(r));
  if (!row) {
    console.error(id ? `#${id} は確認待ちの在庫にない` : '番号を指定する: note-post publish <番号>');
    listStock();
    process.exit(1);
  }
  return { posted, row };
}

function updateTopicStatus(theme, status) {
  const topics = readTable(config.topicsPath);
  const t = topics.rows.find((r) => r.theme === theme && r.status === 'pending');
  if (!t) return;
  t.status = status;
  writeTable(config.topicsPath, topics.header, topics.rows);
}

async function publish({ id, force }) {
  stopIfRequested();
  const { posted, row } = takeFromStock(id);
  if (row.status === 'pending_ng' && !force) {
    console.error(`自己チェックNGの下書き: 「${row.title}」\n指摘: ${row.issues}\n確認の上で公開するなら note-post publish ${row.id} --force`);
    process.exit(1);
  }
  const today = todayJst();
  const already = posted.rows.find((r) => r.published_at === today);
  if (already) {
    log(`本日は公開済み（「${already.title}」）→ 1日1本制限で終了。明日以降に publish を実行`);
    return;
  }

  log(`公開: 「${row.title}」 ${row.draft_url}`);
  const url = await publishDraft({ draftUrl: row.draft_url, tags: row.tags ? row.tags.split(';') : [] });
  Object.assign(row, { status: 'published', url, published_at: today });
  writeTable(config.postedPath, POSTED_HEADER, posted.rows);
  updateTopicStatus(row.theme, 'published');
  log(`公開完了: ${url}`);
  await notifySlack(`公開しました: 「${row.title}」 ${url}`);
}

function reject(id) {
  const { posted, row } = takeFromStock(id);
  row.status = 'rejected';
  writeTable(config.postedPath, POSTED_HEADER, posted.rows);
  updateTopicStatus(row.theme, 'rejected');
  log(`見送り: 「${row.title}」（note上の下書きは残っている。不要なら手動で削除）`);
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  try {
    if (cmd === 'login') await login();
    else if (cmd === 'run') await run({ dryRun: args.includes('--dry-run') });
    else if (cmd === 'list') listStock();
    else if (cmd === 'publish') await publish({ id: args.find((a) => !a.startsWith('--')), force: args.includes('--force') });
    else if (cmd === 'reject') reject(args[0]);
    else {
      console.log('使い方: note-post login | run [--dry-run] | list | publish <番号> [--force] | reject <番号>');
      process.exit(cmd ? 1 : 0);
    }
  } catch (e) {
    const kind = e instanceof LoginExpiredError ? 'ログイン切れ' : e instanceof SelectorError ? 'セレクタ不一致' : 'エラー';
    console.error(`[note-post] ${kind}: ${e.message}`);
    if (cmd === 'run' || cmd === 'publish') await notifySlack(`${kind}で終了: ${e.message}`);
    process.exit(kind === 'エラー' ? 1 : 2);
  }
}

main();
