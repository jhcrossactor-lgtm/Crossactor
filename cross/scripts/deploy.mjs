// クロス デプロイ補助スクリプト
//
//   node scripts/deploy.mjs            … prompt.ts と config.local.js を生成 → chat 関数をデプロイ
//   node scripts/deploy.mjs --secrets  … 上記に加え .env のサーバー側キーを Supabase Secrets に送る
//   node scripts/deploy.mjs --build    … 生成のみ（デプロイしない）
//
// 前提：Node 18+、Supabase CLI がインストール済みで `supabase link` 済み。
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const args = new Set(process.argv.slice(2));

// 1) persona.md + knowledge.md → supabase/functions/chat/prompt.ts
const persona = readFileSync(join(ROOT, "persona.md"), "utf8");
const knowledge = existsSync(join(ROOT, "knowledge.md"))
  ? readFileSync(join(ROOT, "knowledge.md"), "utf8")
  : "";
const promptTs =
  "// 自動生成ファイル。直接編集しない。persona.md / knowledge.md を編集して\n" +
  "// `node scripts/deploy.mjs --build` を実行すること。\n" +
  `export const PERSONA = ${JSON.stringify(persona)};\n` +
  `export const KNOWLEDGE = ${JSON.stringify(knowledge)};\n`;
writeFileSync(join(ROOT, "supabase/functions/chat/prompt.ts"), promptTs);
console.log("✔ supabase/functions/chat/prompt.ts を生成");

// 2) .env → config.local.js（フロント用の公開値のみ）
const envPath = join(ROOT, ".env");
const env = {};
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m || line.trim().startsWith("#")) continue;
    env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  if (env.SUPABASE_URL || env.SUPABASE_ANON_KEY) {
    const local =
      "// 自動生成（.env から）。gitignore 済み。\n" +
      "Object.assign(window.CROSS_CONFIG, {\n" +
      (env.SUPABASE_URL ? `  supabaseUrl: ${JSON.stringify(env.SUPABASE_URL)},\n` : "") +
      (env.SUPABASE_ANON_KEY ? `  supabaseAnonKey: ${JSON.stringify(env.SUPABASE_ANON_KEY)},\n` : "") +
      "});\n";
    writeFileSync(join(ROOT, "config.local.js"), local);
    console.log("✔ config.local.js を生成");
  }
} else {
  console.log("ℹ .env が無いので config.local.js はスキップ（.env.example を参照）");
}

if (args.has("--build")) process.exit(0);

function run(cmd, cmdArgs) {
  console.log(`$ ${cmd} ${cmdArgs.join(" ")}`);
  const r = spawnSync(cmd, cmdArgs, { cwd: ROOT, stdio: "inherit", shell: process.platform === "win32" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

// 3) Secrets（SUPABASE_ で始まるキーは予約語のため送らない）
if (args.has("--secrets")) {
  const pairs = Object.entries(env)
    .filter(([k, v]) => !k.startsWith("SUPABASE_") && v)
    .map(([k, v]) => `${k}=${v}`);
  if (pairs.length === 0) {
    console.error("✖ .env にサーバー側キーが無い");
    process.exit(1);
  }
  run("supabase", ["secrets", "set", ...pairs]);
}

// 4) デプロイ
run("supabase", ["functions", "deploy", "chat"]);
