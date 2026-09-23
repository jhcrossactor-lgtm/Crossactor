import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline/promises';
import { chromium } from 'playwright';
import { marked } from 'marked';
import { config, loadSelectors } from './config.js';

export class LoginExpiredError extends Error {}
export class SelectorError extends Error {}

const baseUrl = process.env.NOTE_BASE_URL; // テスト時にダミー画面へ向ける
const url = (u) => (baseUrl ? new URL(new URL(u).pathname, baseUrl).toString() : u);

function launch(headless) {
  return chromium.launch({ headless, executablePath: config.chromiumPath });
}

export async function login() {
  const sel = loadSelectors();
  const browser = await launch(false);
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(url(sel.urls.login));
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    await rl.question('ブラウザでnoteにログインし、完了したらここでEnterを押してください > ');
    rl.close();
    if (page.url().includes(sel.urls.loginUrlPattern)) {
      throw new LoginExpiredError(`まだログイン画面のまま: ${page.url()}`);
    }
    await context.storageState({ path: config.statePath });
    fs.chmodSync(config.statePath, 0o600);
    console.log(`保存しました: ${config.statePath}`);
  } finally {
    await browser.close();
  }
}

async function need(page, selector, name, timeout = 20000) {
  const loc = page.locator(selector).first();
  try {
    await loc.waitFor({ state: 'visible', timeout });
  } catch {
    // 途中でログイン画面へ飛ばされた場合はセレクタではなくログイン切れとして扱う
    if (page.url().includes(loadSelectors().urls.loginUrlPattern)) {
      throw new LoginExpiredError(`ログイン切れ（ログイン画面へリダイレクト）: ${page.url()}`);
    }
    throw new SelectorError(`セレクタ不一致: ${name} = ${selector} (url=${page.url()})`);
  }
  return loc;
}

// ProseMirrorにMarkdown→HTMLを貼り付けイベントで流し込む（見出し・リスト・太字を保持）
async function pasteMarkdown(page, selector, markdown) {
  if (!markdown.trim()) return;
  const html = marked.parse(markdown);
  await page.evaluate(({ selector, html, markdown }) => {
    const el = document.querySelector(selector);
    el.focus();
    const dt = new DataTransfer();
    dt.setData('text/html', html);
    dt.setData('text/plain', markdown);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  }, { selector, html, markdown });
}

// 本文末尾に空行を作り、エディタの「+」メニュー→画像→ファイル選択でアップロード
async function insertImage(page, sel, file) {
  const imgs = page.locator(sel.image.uploadedImage);
  const before = await imgs.count();
  await page.keyboard.press('Control+End');
  await page.keyboard.press('Enter');
  (await need(page, sel.image.addButton, 'image.addButton')).click();
  const chooserP = page.waitForEvent('filechooser', { timeout: 15000 });
  (await need(page, sel.image.menuItem, 'image.menuItem')).click();
  let chooser;
  try { chooser = await chooserP; } catch {
    throw new SelectorError(`画像メニューからファイル選択が開かない: ${sel.image.menuItem}`);
  }
  await chooser.setFiles(file);
  try {
    await page.waitForFunction(({ s, n }) => document.querySelectorAll(s).length > n,
      { s: sel.image.uploadedImage, n: before }, { timeout: 60000 });
  } catch {
    throw new SelectorError(`画像のアップロード完了を確認できない: ${sel.image.uploadedImage}`);
  }
  await page.keyboard.press('Control+End');
}

// 本文を画像マーカーで分割し、テキスト→画像→テキスト…の順に流し込む
async function fillBody(page, sel, body, images) {
  const bodySel = sel.editor.body;
  await page.locator(bodySel).first().click();
  let rest = body;
  for (const img of images) {
    const at = rest.indexOf(img.marker);
    if (at < 0) continue;
    await pasteMarkdown(page, bodySel, rest.slice(0, at));
    await insertImage(page, sel, img.file);
    rest = rest.slice(at + img.marker.length);
  }
  await pasteMarkdown(page, bodySel, rest);
  const len = await page.locator(bodySel).first().evaluate((el) => el.innerText.trim().length);
  if (len < 50) throw new SelectorError(`本文の流し込みに失敗（${len}字しか入っていない）: ${bodySel}`);
}

// ログイン済みセッションでページを開き、失敗時はスクショを残す共通処理
async function withSession(targetUrl, fn) {
  const sel = loadSelectors();
  if (!fs.existsSync(config.statePath)) {
    throw new LoginExpiredError(`storageStateがない: ${config.statePath}（先に note-post login）`);
  }
  const browser = await launch(config.headless);
  const context = await browser.newContext({ storageState: config.statePath });
  const page = await context.newPage();
  try {
    await page.goto(url(targetUrl), { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    if (page.url().includes(sel.urls.loginUrlPattern)) {
      throw new LoginExpiredError(`ログイン切れ（ログイン画面へリダイレクト）: ${page.url()}`);
    }
    const result = await fn(page, sel);
    // 次回に備えてセッションを更新保存
    await context.storageState({ path: config.statePath });
    return result;
  } catch (e) {
    fs.mkdirSync(config.outDir, { recursive: true });
    const shot = path.join(config.outDir, `error-${Date.now()}.png`);
    await page.screenshot({ path: shot, fullPage: true }).catch(() => {});
    e.message += `\nスクリーンショット: ${shot}`;
    throw e;
  } finally {
    await browser.close();
  }
}

/**
 * 記事（images: 本文中のマーカー位置に差し込む画像）を新規下書きとして保存する。公開はしない。
 * 戻り値: 下書き編集URL
 */
export function saveDraft({ title, body, images = [] }) {
  return withSession(loadSelectors().urls.newNote, async (page, sel) => {
    const titleBox = await need(page, sel.editor.title, 'editor.title');
    await titleBox.fill(title);
    await need(page, sel.editor.body, 'editor.body');
    await fillBody(page, sel, body, images);
    (await need(page, sel.editor.saveDraftButton, 'editor.saveDraftButton')).click();
    await need(page, sel.editor.draftSavedToast, 'editor.draftSavedToast', 15000);
    return page.url();
  });
}

// 有料設定: 有料を選び価格を入れ、区切り文言の直後に有料ラインを置く
async function setPaywall(page, sel, { price, paywallText }) {
  (await need(page, sel.paid.paidOption, 'paid.paidOption')).click();
  await (await need(page, sel.paid.priceInput, 'paid.priceInput')).fill(String(price));
  (await need(page, sel.paid.paywallSettingButton, 'paid.paywallSettingButton')).click();
  await need(page, sel.paid.lineButton, 'paid.lineButton');
  const marker = await page.getByText(paywallText, { exact: false }).last().elementHandle({ timeout: 10000 }).catch(() => null);
  if (!marker) throw new SelectorError(`有料エリア設定画面に区切り文言が見つからない: ${paywallText}`);
  const i = await page.locator(sel.paid.lineButton).evaluateAll(
    (btns, m) => btns.findIndex((b) => m.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING), marker);
  if (i < 0) throw new SelectorError(`区切り文言の後に有料ラインのボタンがない: ${sel.paid.lineButton}`);
  await page.locator(sel.paid.lineButton).nth(i).click();
  if (sel.paid.paywallDoneButton) (await need(page, sel.paid.paywallDoneButton, 'paid.paywallDoneButton')).click();
}

/**
 * 保存済み下書きを開いてそのまま公開する（paid 指定時は有料設定も行う）。本文は触らない（note上での手直しを残すため）。
 * 戻り値: 公開URL
 */
export function publishDraft({ draftUrl, tags = [], paid = null }) {
  return withSession(draftUrl, async (page, sel) => {
    await need(page, sel.editor.title, 'editor.title');
    (await need(page, sel.publish.openPublishButton, 'publish.openPublishButton')).click();
    if (tags.length) {
      const tagInput = await need(page, sel.publish.tagInput, 'publish.tagInput');
      for (const t of tags) {
        await tagInput.fill(t);
        await tagInput.press('Enter');
      }
    }
    if (paid) await setPaywall(page, sel, paid);
    (await need(page, sel.publish.submitButton, 'publish.submitButton')).click();
    try {
      await page.waitForURL((u) => u.pathname.includes(sel.publish.publishedUrlPattern), { timeout: 30000 });
    } catch {
      throw new SelectorError(`公開後のURL遷移を確認できない: ${page.url()}`);
    }
    return page.url();
  });
}
