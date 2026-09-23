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
async function pasteBody(page, selector, markdown) {
  const html = marked.parse(markdown);
  await page.locator(selector).first().click();
  await page.evaluate(({ selector, html, markdown }) => {
    const el = document.querySelector(selector);
    el.focus();
    const dt = new DataTransfer();
    dt.setData('text/html', html);
    dt.setData('text/plain', markdown);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  }, { selector, html, markdown });
  const len = await page.locator(selector).first().evaluate((el) => el.innerText.trim().length);
  if (len < 50) throw new SelectorError(`本文の流し込みに失敗（${len}字しか入っていない）: ${selector}`);
}

/**
 * 記事を下書き保存し、publish=true なら続けて公開する。
 * 戻り値: { draftUrl, publishedUrl|null }
 */
export async function postToNote({ title, body, tags = [], publish = false }) {
  const sel = loadSelectors();
  if (!fs.existsSync(config.statePath)) {
    throw new LoginExpiredError(`storageStateがない: ${config.statePath}（先に note-post login）`);
  }
  const browser = await launch(config.headless);
  const context = await browser.newContext({ storageState: config.statePath });
  const page = await context.newPage();
  try {
    await page.goto(url(sel.urls.newNote), { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    if (page.url().includes(sel.urls.loginUrlPattern)) {
      throw new LoginExpiredError(`ログイン切れ（ログイン画面へリダイレクト）: ${page.url()}`);
    }

    const titleBox = await need(page, sel.editor.title, 'editor.title');
    await titleBox.fill(title);
    await need(page, sel.editor.body, 'editor.body');
    await pasteBody(page, sel.editor.body, body);

    (await need(page, sel.editor.saveDraftButton, 'editor.saveDraftButton')).click();
    await need(page, sel.editor.draftSavedToast, 'editor.draftSavedToast', 15000);
    const draftUrl = page.url();

    // 失敗時の再ログイン・再開に備えてセッションを更新保存
    await context.storageState({ path: config.statePath });

    if (!publish) return { draftUrl, publishedUrl: null };

    (await need(page, sel.publish.openPublishButton, 'publish.openPublishButton')).click();
    if (tags.length) {
      const tagInput = await need(page, sel.publish.tagInput, 'publish.tagInput');
      for (const t of tags) {
        await tagInput.fill(t);
        await tagInput.press('Enter');
      }
    }
    (await need(page, sel.publish.submitButton, 'publish.submitButton')).click();
    try {
      await page.waitForURL((u) => u.pathname.includes(sel.publish.publishedUrlPattern), { timeout: 30000 });
    } catch {
      throw new SelectorError(`公開後のURL遷移を確認できない: ${page.url()}`);
    }
    return { draftUrl, publishedUrl: page.url() };
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
