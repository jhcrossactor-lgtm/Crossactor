import fs from 'node:fs';
import { config } from './config.js';
import { readTable } from './csv.js';

export function loadEditorial() {
  const e = JSON.parse(fs.readFileSync(config.genresPath, 'utf8'));
  e.affiliates = readTable(config.affiliatesPath).rows.filter((r) => r.id && r.url);
  return e;
}

export const genreById = (ed, id) => ed.genres.find((g) => g.id === id);

// アフィリエイトジャンルは商品リストが空なら書けないので対象外
export function activeGenres(ed) {
  return ed.genres.filter((g) => g.enabled && (!g.affiliate || ed.affiliates.length));
}

/**
 * ローテーション: 前回生成したジャンルの次から順に、未処理トピックがあるジャンルを選ぶ。
 * 戻り値: topics.rows のインデックス（なければ -1）
 */
export function pickTopic(ed, topicRows, lastGenreId) {
  const genres = activeGenres(ed);
  if (!genres.length) return -1;
  const start = (genres.findIndex((g) => g.id === lastGenreId) + 1) % genres.length;
  for (let k = 0; k < genres.length; k++) {
    const g = genres[(start + k) % genres.length];
    const i = topicRows.findIndex((r) => !r.status?.trim() && (r.genre || genres[0].id) === g.id);
    if (i >= 0) return i;
  }
  return -1;
}

const AFF = /^<!--\s*affiliate:\s*([\w-]+)\s*-->$/gm;
const PAYWALL = /^<!--\s*paywall\s*-->$/gm;

/**
 * 記事のジャンル規則を機械的に検査し、マーカーを本文に展開する。
 * - affiliate: IDをaffiliates.csvのリンクに置換、先頭にPR表記。本文中の生URLは禁止
 * - paid: paywallマーカーがちょうど1つ。区切り文言に置換
 * 戻り値: { body, issues }（issues は自己チェックと同じ形式）
 */
export function applyGenreRules(ed, genre, body) {
  const issues = [];
  const add = (excerpt, reason) => issues.push({ category: 'rule', excerpt, reason });

  const raw = body.replace(/<!--[\s\S]*?-->/g, '').match(/https?:\/\/[^\s)>\]]+/g);
  if (raw) add(raw.join(' '), 'AIが書いたURLが含まれている（リンクは affiliates.csv 経由のみ）');

  const affIds = [...body.matchAll(AFF)].map((m) => m[1]);
  if (genre.affiliate) {
    if (!affIds.length) add('(なし)', 'アフィリエイト記事なのに商品リンクがない');
    body = body.replace(AFF, (m, id) => {
      const a = ed.affiliates.find((x) => x.id === id);
      if (!a) { add(m, `affiliates.csv にないID: ${id}`); return ''; }
      return `[${a.name}（PR）](${a.url})`;
    });
    if (affIds.length) body = `${ed.prNotice}\n\n${body}`;
  } else if (affIds.length) {
    add(affIds.join(','), 'アフィリエイト対象外のジャンルに商品リンクがある');
    body = body.replace(AFF, '');
  }

  const walls = body.match(PAYWALL) || [];
  if (genre.paid?.enabled) {
    if (walls.length !== 1) add(`paywall ${walls.length}個`, '有料記事の区切りがちょうど1つではない');
    else {
      const free = body.split(PAYWALL)[0].replace(/<!--[\s\S]*?-->/g, '').trim();
      if (free.length < 400) add(`無料部分${free.length}字`, '無料部分が短すぎて内容が伝わらない');
    }
    body = body.replace(PAYWALL, ed.paywallText);
  } else if (walls.length) {
    add('paywall', '無料ジャンルに有料区切りがある');
    body = body.replace(PAYWALL, '');
  }
  return { body: body.replace(/\n{3,}/g, '\n\n'), issues };
}

