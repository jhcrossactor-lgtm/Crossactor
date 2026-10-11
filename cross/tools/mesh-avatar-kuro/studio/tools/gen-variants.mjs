// 差分絵 7 枚（目閉じ・半目・笑い目・あ・あ半・い・お）を OpenAI 画像編集 API で生成し、
// マスクの内側だけ source.png に合成して variants/ に入れ、スプライトを作り直す。
//
//   node tools/gen-variants.mjs projects/kuro                 … 7 枚全部（既にある差分は飛ばす）
//   node tools/gen-variants.mjs projects/kuro eyes_closed mouth_a
//   node tools/gen-variants.mjs projects/kuro --ref "C:\Users\me\Desktop\sheet.png"   … 絵柄の参照画像を添える
//   node tools/gen-variants.mjs projects/kuro --no-build      … 生成と合成だけ（build-sprites / render-poses を回さない）
//   node tools/gen-variants.mjs projects/kuro --redo mouth_i  … その差分だけ作り直す
//
// 前提：mesh-avatar-studio の直下で実行。Node 22+、uv。先に
//   uv run tools/variant-requests.py projects/kuro
// でマスクを作っておく。
// キー：環境変数 OPENAI_API_KEY、無ければ --env で指定した .env（既定 G:\ClaudeLocal\cross\.env、無ければ ./.env）。
// キーは画面に出さない。生の生成画像は projects/<name>/variants_raw/ に残す（git には入らない）。
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { basename, join, resolve } from 'node:path';

const VARIANTS = {
  eyes_closed: '両目を自然に閉じる。片目につき上まつ毛の線1本だけの、きれいな閉じ目。線の太さは元の上まつ毛と同じ。虹彩と白目は完全に消す。閉じ目の位置は元の目の中心より少し下。',
  eyes_half: '両目を半分閉じる。上まぶたを目の高さの半分まで下ろし、虹彩は上まぶたの下にだけ見える。視線の向きと虹彩の色は元のまま。眠そうではなく、冷静に見下ろす半目。',
  eyes_smile: '両目を「にっこり」の上向きの弧で閉じる。片目につき弧の線1本、まつ毛はきれいに、虹彩も白目も見せない。弧は控えめで、大人の微笑み程度。',
  mouth_a: '口を日本語の「あ」で縦に開ける。自然な開き方で、上の歯を少しと舌をわずかに見せる。開きは控えめ（口の高さは元の口幅の半分程度まで）。顎の輪郭と位置は変えない。口の中は暗い赤系で派手にしない。',
  mouth_a_half: '口を日本語の「あ」の半分の開きにする。小さく、やわらかく開いた口。歯はほんの少し見える程度、舌は見せない。顎の輪郭は変えない。',
  mouth_i: '口を日本語の「い」にする。横に広く、縦に狭く開いた口。上の歯が一列に少し見える。口角は元の位置より少しだけ外側。顎の輪郭は変えない。',
  mouth_o: '口を日本語の「お」にする。小さく丸く開いた口。口の中は暗く、歯はほぼ見せない。口の幅は元の口幅より狭い。顎の輪郭は変えない。',
};
const COMMON = (name) =>
  `2Dアバター用の立ち絵の部分編集。マスクの透明な部分（${name.startsWith('eyes') ? '両目の周り' : '口の周り'}）だけを描き直し、それ以外は1ピクセルも変えない。` +
  `${name.startsWith('eyes') ? '眼鏡のフレームとレンズの縁、眉、髪、' : '鼻、顎の輪郭、'}肌色、顔の輪郭、服、透過背景はそのまま。` +
  '絵柄は元絵どおり（硬質で清潔な線、青いホログラムの光沢のアニメ調）。変更はマスクの縁から4ピクセル以上内側に収める。切り抜き・リサイズ・位置ずらし禁止。\n\n';

// ---- 引数 ----
const args = process.argv.slice(2);
const flags = new Set(), opts = {}, names = [];
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--ref' || a === '--env' || a === '--model' || a === '--quality' || a === '--size') opts[a.slice(2)] = args[++i];
  else if (a === '--redo') { flags.add('redo'); }
  else if (a.startsWith('--')) flags.add(a.slice(2));
  else names.push(a);
}
const project = names.shift();
if (!project || !existsSync(join(project, 'source.png'))) {
  console.error('使い方: node tools/gen-variants.mjs projects/<name> [差分名...] [--ref 参照画像] [--no-build] [--redo]');
  process.exit(1);
}
const wanted = names.length ? names : Object.keys(VARIANTS);
for (const n of wanted) if (!VARIANTS[n]) { console.error(`知らない差分名: ${n}（${Object.keys(VARIANTS).join(', ')}）`); process.exit(1); }

// ---- キー ----
function loadEnv(path) {
  const env = {};
  if (!existsSync(path)) return env;
  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !line.trim().startsWith('#')) env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
  return env;
}
const envPath = opts.env ?? (existsSync('G:\\ClaudeLocal\\cross\\.env') ? 'G:\\ClaudeLocal\\cross\\.env' : '.env');
const env = loadEnv(envPath);
const apiKey = process.env.OPENAI_API_KEY || env.OPENAI_API_KEY;
if (!apiKey) { console.error(`✖ OPENAI_API_KEY が無い（環境変数か ${envPath}）`); process.exit(1); }
const model = opts.model || env.OPENAI_IMAGE_MODEL || 'gpt-image-1';
const quality = opts.quality || env.OPENAI_IMAGE_QUALITY || 'high';
const size = opts.size || '1024x1536';   // 縦長。source のサイズとは違っていてよい（合成時に戻す）

// ---- 生成 ----
const rawDir = join(project, 'variants_raw');
mkdirSync(rawDir, { recursive: true });
const source = readFileSync(join(project, 'source.png'));
const ref = opts.ref ? readFileSync(opts.ref) : null;
const uv = (...a) => spawnSync('uv', a, { stdio: 'inherit', shell: process.platform === 'win32' });

let ok = 0, skipped = 0, failed = [];
for (const name of wanted) {
  const raw = join(rawDir, `${name}.png`), dest = join(project, 'variants', `${name}.png`);
  if (existsSync(dest) && !flags.has('redo')) { console.log(`– ${name} 既にある（作り直すなら --redo）`); skipped++; continue; }
  const maskPath = join(project, 'variant-requests', name, 'mask.png');
  if (!existsSync(maskPath)) { console.log(`✖ ${name} マスクが無い。先に uv run tools/variant-requests.py ${project}`); failed.push(name); continue; }
  process.stdout.write(`… ${name} 生成中 `);
  try {
    const form = new FormData();
    form.append('model', model);
    form.append('prompt', COMMON(name) + VARIANTS[name]);
    form.append('size', size);
    form.append('quality', quality);
    form.append('n', '1');
    // image[] の先頭が編集対象。mask は「透明 = 編集してよい」で、mesh-avatar-studio のマスクと同じ向き
    form.append('image[]', new Blob([source], { type: 'image/png' }), 'source.png');
    if (ref) form.append('image[]', new Blob([ref], { type: 'image/png' }), basename(opts.ref));
    form.append('mask', new Blob([readFileSync(maskPath)], { type: 'image/png' }), 'mask.png');
    const res = await fetch('https://api.openai.com/v1/images/edits', { method: 'POST', headers: { authorization: `Bearer ${apiKey}` }, body: form });
    if (!res.ok) {
      const text = (await res.text()).slice(0, 300);
      console.log(`✖ HTTP ${res.status} ${text}`);
      failed.push(name);
      if (res.status === 401 || res.status === 429) break;
      continue;
    }
    const data = await res.json();
    const d = data.data?.[0] ?? {};
    const buf = d.b64_json ? Buffer.from(d.b64_json, 'base64') : d.url ? Buffer.from(await (await fetch(d.url)).arrayBuffer()) : null;
    if (!buf) { console.log('✖ 画像が返ってこなかった'); failed.push(name); continue; }
    writeFileSync(raw, buf);
    console.log(`✔ ${Math.round(buf.length / 1024)} KB → 合成`);
    const r = uv('run', '--quiet', 'tools/merge-variant.py', project, name, raw);
    if (r.status !== 0) { failed.push(name); continue; }
    ok++;
  } catch (e) {
    console.log(`✖ ${e?.message ?? e}`); failed.push(name);
  }
}
console.log(`\n生成 ${ok} / 既存 ${skipped} / 失敗 ${failed.length}${failed.length ? '：' + failed.join(', ') : ''}`);

if (!flags.has('no-build') && (ok > 0)) {
  console.log('\n→ build-sprites');
  uv('run', '--quiet', '--with', 'numpy', '--with', 'pillow', '--with', 'opencv-python-headless', 'tools/build-sprites.py', project);
  console.log('→ render-poses');
  spawnSync('npm', ['run', 'render-poses', '--', project], { stdio: 'inherit', shell: true });
  console.log(`\n確認: ${resolve(project, 'review')} の目閉じ・口のコマを見る。二重に見える差分は --redo で作り直すか、merge-variant.py --shift で位置を合わせる`);
}
process.exit(failed.length && ok === 0 ? 1 : 0);
