// クロ用の追加ファイルを mesh-avatar-studio の clone に入れる（本体のファイルは一切上書きしない）
//
//   node install.mjs G:\ClaudeLocal\mesh-avatar-studio
//
// 入れるもの：
//   stream-fx.html            クロ用の配信ページ（粒子エフェクト＋落ち着いた待機動作）
//   src/fx/*                  エフェクト本体・設定・型・ページのスクリプト
//   tools/merge-variant.py    ChatGPT の差分絵をマスク内側だけ合成するツール
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const target = resolve(process.argv[2] ?? '');
if (!process.argv[2] || !existsSync(join(target, 'package.json')) || !existsSync(join(target, 'docs', 'agent-guide.md'))) {
  console.error('使い方: node install.mjs <mesh-avatar-studio の clone フォルダ>');
  process.exit(1);
}
// 調整済みの設定ファイルは上書きしない（再実行しても粒子の設定が初期値に戻らないように）
const KEEP = new Set(['src/fx/digital-rise.config.js']);
const copies = [
  ['studio/stream-fx.html', 'stream-fx.html'],
  ...readdirSync(join(HERE, 'studio/src/fx')).map(name => [`studio/src/fx/${name}`, `src/fx/${name}`]),
  ['studio/tools/merge-variant.py', 'tools/merge-variant.py'],
];
for (const [from, to] of copies) {
  const src = join(HERE, from), dest = join(target, to);
  if (KEEP.has(to) && existsSync(dest)) { console.log(`– ${to}（既にあるので残す。初期値に戻すなら消してから再実行）`); continue; }
  mkdirSync(dirname(dest), { recursive: true });
  cpSync(src, dest, { recursive: true, force: true });
  console.log(`✔ ${to}${statSync(src).isDirectory() ? '/' : ''}`);
}
const vite = readFileSync(join(target, 'vite.config.ts'), 'utf8');
if (!vite.includes('stream-fx.html')) {
  console.log('ℹ 開発サーバー（npm run dev）はこのままで http://127.0.0.1:5173/stream-fx.html?project=kuro が開ける。');
  console.log('  本番ビルド（npm run build）にも含めたい時だけ vite.config.ts の rollupOptions.input に `fx: \'stream-fx.html\'` を足す。');
}
console.log('完了。確認: npm run dev → http://127.0.0.1:5173/stream-fx.html?project=kuro');
