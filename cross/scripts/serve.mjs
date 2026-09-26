// ローカル配信サーバー（依存なし）
//   node scripts/serve.mjs        → http://localhost:8787 で index.html を配信
// VOICEVOX（127.0.0.1:50021）への接続や、マイク許可（Web Speech API）は file:// では通らないため、
// 開発・撮影時はこのサーバー経由でブラウザに開く。
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PORT = Number(process.env.PORT || 8787);
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp",
  ".svg": "image/svg+xml", ".glb": "model/gltf-binary", ".md": "text/markdown; charset=utf-8", ".mp3": "audio/mpeg", ".wav": "audio/wav",
};

createServer(async (req, res) => {
  const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
  let rel = normalize(urlPath).replace(/^(\.\.[/\\])+/, "");
  if (rel === "/" || rel === "\\") rel = "/index.html";
  if (/(^|[/\\])\.env/.test(rel)) { res.writeHead(403); res.end("forbidden"); return; }   // .env は絶対に配信しない
  const file = join(ROOT, rel);
  if (!file.startsWith(ROOT)) { res.writeHead(403); res.end("forbidden"); return; }   // ルート外は配信しない
  try {
    const st = await stat(file);
    if (!st.isFile()) throw new Error("not file");
    res.writeHead(200, { "Content-Type": TYPES[extname(file).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("not found: " + rel);
  }
}).listen(PORT, "127.0.0.1", () => {
  console.log(`クロス: http://localhost:${PORT}  （終了は Ctrl+C）`);
});
