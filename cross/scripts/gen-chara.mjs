// クロ キャラ候補の一括生成（OpenAI 画像API）
// テイスト別：01-08 初期案 / 09-20 追加案 / 21-32 テイスト拡張（レトロ・ドット・アメコミ・SD・サイバーパンク・水墨・クレイ・切り絵・線画・油彩・ノワール・青図面）
//
//   node scripts/gen-chara.mjs             … assets/chara/prompts.json の 32 案を全部生成
//   node scripts/gen-chara.mjs 9-20        … 番号範囲だけ
//   node scripts/gen-chara.mjs 3,7,12      … 番号指定
//   node scripts/gen-chara.mjs --list      … 一覧だけ表示（生成しない）
//
// 前提：Node 18+。.env に OPENAI_API_KEY（ChatGPT の月額とは別の API キー。platform.openai.com で発行）。
// 出力：assets/chara/candidates/NN_slug.png（既にあるファイルは飛ばす。作り直すなら削除してから）
// キーは画面に一切出さない。
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "assets/chara/candidates");
const args = process.argv.slice(2);

const env = {};
const envPath = join(ROOT, ".env");
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m || line.trim().startsWith("#")) continue;
    env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}
const apiKey = process.env.OPENAI_API_KEY || env.OPENAI_API_KEY;
const model = process.env.OPENAI_IMAGE_MODEL || env.OPENAI_IMAGE_MODEL || "gpt-image-1";
const size = env.OPENAI_IMAGE_SIZE || "1024x1536"; // 縦長（4:5 相当に近い）
const quality = env.OPENAI_IMAGE_QUALITY || "medium"; // low / medium / high

const { common, items } = JSON.parse(readFileSync(join(ROOT, "assets/chara/prompts.json"), "utf8"));

// 番号の選択
let selected = items;
const spec = args.find((a) => !a.startsWith("--"));
if (spec) {
  const want = new Set();
  for (const part of spec.split(",")) {
    const r = part.match(/^(\d+)-(\d+)$/);
    if (r) for (let i = +r[1]; i <= +r[2]; i++) want.add(i);
    else if (/^\d+$/.test(part)) want.add(+part);
  }
  selected = items.filter((it) => want.has(+it.no));
}

if (args.includes("--list")) {
  for (const it of items) console.log(`${it.no}  ${it.slug}`);
  process.exit(0);
}
if (!apiKey) {
  console.error("✖ OPENAI_API_KEY がありません。.env に追記してください（.env.example 参照）");
  process.exit(1);
}
mkdirSync(OUT, { recursive: true });
console.log(`モデル: ${model} / サイズ: ${size} / 品質: ${quality} / ${selected.length} 枚`);

let ok = 0, skip = 0, ng = 0;
for (const it of selected) {
  const file = join(OUT, `${it.no}_${it.slug}.png`);
  if (existsSync(file)) { console.log(`– ${it.no} 既にあるので飛ばす`); skip++; continue; }
  process.stdout.write(`… ${it.no} ${it.slug} `);
  try {
    const res = await fetch("https://api.openai.com/v1/images/generations", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model, size, quality, n: 1,
        prompt: `${common}\n\n${it.prompt}`,
      }),
    });
    if (!res.ok) {
      const text = (await res.text()).slice(0, 300);
      console.log(`✖ HTTP ${res.status} ${text}`);
      ng++;
      if (res.status === 401 || res.status === 429) break; // キー不正・残高切れは以降も失敗するので止める
      continue;
    }
    const data = await res.json();
    const d = data.data?.[0] ?? {};
    let buf;
    if (d.b64_json) buf = Buffer.from(d.b64_json, "base64");
    else if (d.url) buf = Buffer.from(await (await fetch(d.url)).arrayBuffer());
    else { console.log("✖ 画像データが返ってこなかった"); ng++; continue; }
    writeFileSync(file, buf);
    console.log(`✔ ${Math.round(buf.length / 1024)} KB`);
    ok++;
  } catch (e) {
    console.log(`✖ ${e?.message ?? e}`);
    ng++;
  }
}
console.log(`\n完了: 成功 ${ok} / 既存 ${skip} / 失敗 ${ng} → ${OUT}`);
