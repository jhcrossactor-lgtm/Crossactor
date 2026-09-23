import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// 全パスは環境変数で上書き可能（テスト・別アカウント運用用）
export const config = {
  root: ROOT,
  statePath: process.env.NOTE_STATE_PATH || path.join(os.homedir(), '.note-state.json'),
  topicsPath: process.env.NOTE_TOPICS_PATH || path.join(ROOT, 'topics.csv'),
  postedPath: process.env.NOTE_POSTED_PATH || path.join(ROOT, 'posted.csv'),
  stopPath: process.env.NOTE_STOP_PATH || path.join(ROOT, 'STOP'),
  outDir: process.env.NOTE_OUT_DIR || path.join(ROOT, 'out'),
  selectorsPath: process.env.NOTE_SELECTORS_PATH || path.join(ROOT, 'selectors.json'),
  model: process.env.NOTE_POST_MODEL || 'claude-opus-5',
  slackWebhook: process.env.SLACK_WEBHOOK_URL || '',
  headless: process.env.NOTE_HEADLESS !== '0',
  chromiumPath: process.env.NOTE_CHROMIUM_PATH || undefined,
  mockLlm: process.env.NOTE_POST_MOCK_LLM === '1',
};

export function loadSelectors() {
  return JSON.parse(fs.readFileSync(config.selectorsPath, 'utf8'));
}

// 1日1本の判定はJST基準
export function todayJst() {
  return new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
}
