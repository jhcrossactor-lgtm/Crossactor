#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { config, todayJst } from './config.js';
import { readTable, writeTable, appendRow } from './csv.js';
import { generateArticle, checkArticle } from './llm.js';
import { login, postToNote, LoginExpiredError, SelectorError } from './note.js';
import { notifySlack } from './slack.js';
import { generateImages, stripImageMarkers } from './images.js';

const POSTED_HEADER = ['date', 'status', 'theme', 'title', 'url', 'issues'];
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
    const done = readTable(config.postedPath).rows.filter((r) => r.date === today && r.status !== 'dry_run');
    if (done.length) {
      log(`本日（${today}）は処理済み（${done[0].status}）→ 1日1本制限で終了`);
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

  const publish = check.ok && !dryRun;
  const { draftUrl, publishedUrl } = await postToNote({ ...article, images, tags, publish });
  const status = dryRun ? 'dry_run' : publish ? 'published' : 'draft_ng';
  const url = publishedUrl || draftUrl;
  log(`${status}: ${url}`);

  appendRow(config.postedPath, POSTED_HEADER, {
    date: today, status, theme: topic.theme, title: article.title, url,
    issues: check.issues.map((i) => `[${i.category}]${i.reason}`).join(' / '),
  });
  if (!dryRun) {
    topic.status = status;
    writeTable(config.topicsPath, topics.header, topics.rows);
  }
  if (status === 'draft_ng') await notifySlack(`自己チェックNGのため下書き保存のみ: 「${article.title}」 ${url}`);
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  try {
    if (cmd === 'login') await login();
    else if (cmd === 'run') await run({ dryRun: args.includes('--dry-run') });
    else {
      console.log('使い方: note-post login | note-post run [--dry-run]');
      process.exit(cmd ? 1 : 0);
    }
  } catch (e) {
    const kind = e instanceof LoginExpiredError ? 'ログイン切れ' : e instanceof SelectorError ? 'セレクタ不一致' : 'エラー';
    console.error(`[note-post] ${kind}: ${e.message}`);
    if (cmd === 'run') await notifySlack(`${kind}で終了: ${e.message}`);
    process.exit(kind === 'エラー' ? 1 : 2);
  }
}

main();
