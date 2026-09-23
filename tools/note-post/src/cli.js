#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { config, todayJst } from './config.js';
import { readTable, writeTable, appendRow } from './csv.js';
import { generateArticle, checkArticle, proposeTopics } from './llm.js';
import { loadEditorial, genreById, activeGenres, pickTopic, applyGenreRules } from './editorial.js';
import { login, saveDraft, publishDraft, LoginExpiredError, SelectorError } from './note.js';
import { notifySlack } from './slack.js';
import { generateImages, stripImageMarkers } from './images.js';

const POSTED_HEADER = ['id', 'date', 'status', 'genre', 'paid', 'theme', 'title', 'tags', 'draft_url', 'url', 'issues', 'published_at'];
// 確認待ち: pending（チェックOK）/ pending_ng（チェックNG）
const isPending = (r) => r.status === 'pending' || r.status === 'pending_ng';
const TOPIC_HEADER = ['genre', 'theme', 'reader', 'message', 'tags', 'status'];
const PROPOSAL_HEADER = ['id', 'date', 'status', 'genre', 'theme', 'reader', 'message', 'tags', 'reason'];
const TOPIC_LOW = Number(process.env.NOTE_TOPIC_LOW ?? 2); // ジャンルごとの未処理テーマがこれ未満なら提案
const PROPOSE_PER_GENRE = Number(process.env.NOTE_PROPOSE_PER_GENRE ?? 3);
const parseTags = (s) => (s || '').split(/[;；、]/).map((t) => t.trim().replace(/^#/, '')).filter(Boolean);
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

  const ed = loadEditorial();
  const topics = readTable(config.topicsPath);
  for (const h of TOPIC_HEADER) if (!topics.header.includes(h)) topics.header.push(h);
  const lastGenre = readTable(config.postedPath).rows.filter((r) => r.status !== 'dry_run').at(-1)?.genre;
  const idx = pickTopic(ed, topics.rows, lastGenre);
  if (idx < 0) {
    log('書ける未処理テーマがない → テーマ提案だけして終了');
    if (!dryRun) await maybePropose(ed, topics.rows);
    return;
  }
  const topic = topics.rows[idx];
  const genre = genreById(ed, topic.genre || activeGenres(ed)[0].id);
  const tags = parseTags(topic.tags);
  log(`対象: [${genre.name}${genre.paid?.enabled ? '・有料' : ''}] ${topic.theme}${dryRun ? '（dry-run）' : ''}`);

  const article = await generateArticle(topic, ed, genre);
  log(`生成完了: 「${article.title}」 本文${article.body.length}字`);
  if (article.body.length < 1500 || article.body.length > 4000) log(`警告: 本文字数が想定外（${article.body.length}字）`);

  const check = await checkArticle(article, ed, genre);
  // 有料区切り・アフィリエイトリンク・PR表記は機械的に検査・展開する
  const rule = applyGenreRules(ed, genre, article.body);
  article.body = rule.body;
  check.issues.push(...rule.issues);
  if (rule.issues.length) check.ok = false;
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
    id, date: today, status, genre: genre.id, paid: genre.paid?.enabled ? '1' : '', theme: topic.theme, title: article.title, tags: tags.join(';'),
    draft_url: draftUrl, url: '', issues: issues.join(' / '), published_at: '',
  });
  if (dryRun) return;

  topic.status = 'pending';
  writeTable(config.topicsPath, topics.header, topics.rows);
  const stock = prev.filter(isPending).length + 1;
  const kind = `[${genre.name}${genre.paid?.enabled ? '・有料' : ''}]`;
  const head = check.ok
    ? `在庫追加 #${id} ${kind}（自己チェックOK）`
    : `在庫追加 #${id} ${kind}（⚠自己チェックNG ${issues.length}件）\n${issues.map((i) => `・${i}`).join('\n')}\n公開するなら \`note-post publish ${id} --force\``;
  await notifySlack(`${head}\n「${article.title}」\n${draftUrl}\n確認待ち在庫: ${stock}本。一覧は \`note-post list\`、公開は \`note-post publish <番号>\``);
  await maybePropose(ed, topics.rows);
}

// ---- テーマ提案（AIが出す → ほせもやんが accept したものだけ topics.csv へ）----

const openProposals = () => readTable(config.proposalsPath).rows.filter((r) => r.status === 'open');

// 未処理テーマが少ないジャンルがあり、未回答の提案がなければ提案する。失敗しても run は止めない
async function maybePropose(ed, topicRows) {
  if (openProposals().length) return;
  const low = activeGenres(ed).filter((g) =>
    topicRows.filter((r) => !r.status?.trim() && (r.genre || activeGenres(ed)[0].id) === g.id).length < TOPIC_LOW);
  if (!low.length) return;
  try {
    await propose(ed, low, PROPOSE_PER_GENRE);
  } catch (e) {
    log(`テーマ提案に失敗: ${e.message}`);
    await notifySlack(`テーマ提案に失敗: ${e.message}`);
  }
}

async function propose(ed, genres, perGenre) {
  const topics = readTable(config.topicsPath).rows.map((r) => r.theme);
  const past = readTable(config.proposalsPath).rows.map((r) => r.theme);
  const list = await proposeTopics(ed, genres, perGenre, [...topics, ...past]);
  const prev = readTable(config.proposalsPath).rows;
  let next = Math.max(0, ...prev.map((r) => Number(r.id) || 0));
  const today = todayJst();
  const added = list.map((t) => ({ id: String(++next), date: today, status: 'open', ...t }));
  for (const r of added) appendRow(config.proposalsPath, PROPOSAL_HEADER, r);
  log(`テーマ案 ${added.length}件を追加`);
  const name = (id) => genreById(ed, id)?.name ?? id;
  await notifySlack(`テーマ案 ${added.length}件\n${added.map((r) => `#${r.id} [${name(r.genre)}] ${r.theme}（${r.reason}）`).join('\n')}\n採用は \`note-post accept <番号...>\`、不採用は \`note-post decline <番号...>\``);
  listProposals();
}

function listProposals() {
  const open = openProposals();
  if (!open.length) return log('未回答のテーマ案はない');
  console.log(`テーマ案 ${open.length}件（採用: note-post accept <番号...> / 不採用: note-post decline <番号...>）`);
  for (const r of open) console.log(`#${r.id}  [${r.genre}] ${r.theme}\n     読者: ${r.reader} / 伝えること: ${r.message} / タグ: ${r.tags}`);
}

function answerProposals(ids, accept) {
  if (!ids.length) { console.error('番号を指定する'); listProposals(); process.exit(1); }
  const p = readTable(config.proposalsPath);
  const topics = readTable(config.topicsPath);
  for (const h of TOPIC_HEADER) if (!topics.header.includes(h)) topics.header.push(h);
  for (const id of ids) {
    const r = p.rows.find((x) => x.id === id && x.status === 'open');
    if (!r) { console.error(`#${id} は未回答のテーマ案にない`); continue; }
    r.status = accept ? 'accepted' : 'declined';
    if (accept) topics.rows.push({ genre: r.genre, theme: r.theme, reader: r.reader, message: r.message, tags: r.tags, status: '' });
    log(`${accept ? '採用' : '不採用'}: #${id} ${r.theme}`);
  }
  writeTable(config.proposalsPath, PROPOSAL_HEADER, p.rows);
  if (accept) writeTable(config.topicsPath, topics.header, topics.rows);
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

  let paid = null;
  if (row.paid === '1') {
    const ed = loadEditorial();
    const genre = genreById(ed, row.genre);
    const price = Number(genre?.paid?.price);
    if (!price) {
      console.error(`有料記事の価格が未設定: genres.json の ${row.genre}.paid.price を決めてから publish する`);
      process.exit(1);
    }
    paid = { price, paywallText: ed.paywallText };
  }

  log(`公開: 「${row.title}」${paid ? `（有料 ${paid.price}円）` : ''} ${row.draft_url}`);
  const url = await publishDraft({ draftUrl: row.draft_url, tags: parseTags(row.tags), paid });
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
    else if (cmd === 'propose') await propose(loadEditorial(), activeGenres(loadEditorial()), Number(args[0]) || PROPOSE_PER_GENRE);
    else if (cmd === 'proposals') listProposals();
    else if (cmd === 'accept') answerProposals(args, true);
    else if (cmd === 'decline') answerProposals(args, false);
    else {
      console.log(`使い方:
  note-post login
  note-post run [--dry-run]            記事を1本作って在庫へ
  note-post list                       確認待ち在庫
  note-post publish <番号> [--force]    在庫を公開
  note-post reject <番号>               在庫を見送り
  note-post propose [ジャンルごとの件数]   テーマ案を出す
  note-post proposals                  未回答のテーマ案
  note-post accept|decline <番号...>    テーマ案を採用 / 不採用`);
      process.exit(cmd ? 1 : 0);
    }
  } catch (e) {
    const kind = e instanceof LoginExpiredError ? 'ログイン切れ' : e instanceof SelectorError ? 'セレクタ不一致' : 'エラー';
    console.error(`[note-post] ${kind}: ${e.message}`);
    if (['run', 'publish', 'propose'].includes(cmd)) await notifySlack(`${kind}で終了: ${e.message}`);
    process.exit(kind === 'エラー' ? 1 : 2);
  }
}

main();
