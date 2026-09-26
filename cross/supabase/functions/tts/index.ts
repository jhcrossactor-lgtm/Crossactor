// /tts — Azure Speech（REST）で1文を mp3 にして返す
//
// 入力（POST JSON）: { text: string, voice?: string, style?: string, rate?: string, pitch?: string }
// 出力: audio/mpeg（24kHz 48kbps mono）
import { gate, json, CORS } from "../_shared/auth.ts";

const MAX_CHARS = 400;
const DEFAULT_VOICE = Deno.env.get("TTS_VOICE") ?? "ja-JP-KeitaNeural";

function xmlEscape(s: string): string {
  return s.replace(/[<>&'"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c]!));
}
const VOICE_RE = /^[A-Za-z]{2}-[A-Za-z]{2,4}-[A-Za-z0-9]+Neural$/;
const STYLE_RE = /^[a-z-]{2,32}$/;
const PROSODY_RE = /^[+-]?\d{1,3}(\.\d+)?%$/;

function buildSsml(text: string, voice: string, style: string, rate: string, pitch: string): string {
  const inner = `<prosody rate="${rate}" pitch="${pitch}">${xmlEscape(text)}</prosody>`;
  const styled = style ? `<mstts:express-as style="${style}">${inner}</mstts:express-as>` : inner;
  return `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="ja-JP">` +
    `<voice name="${voice}">${styled}</voice></speak>`;
}

Deno.serve(async (req) => {
  const blocked = gate(req);
  if (blocked) return blocked;

  const key = Deno.env.get("AZURE_SPEECH_KEY");
  const region = Deno.env.get("AZURE_SPEECH_REGION");
  if (!key || !region) return json(503, { error: "AZURE_SPEECH_KEY / AZURE_SPEECH_REGION が Secrets に未設定", code: "tts_unconfigured" });

  let body: { text?: unknown; voice?: unknown; style?: unknown; rate?: unknown; pitch?: unknown };
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "JSON body が必要" });
  }
  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!text) return json(400, { error: "text が空" });
  if (text.length > MAX_CHARS) return json(400, { error: `text が長すぎる（最大${MAX_CHARS}文字）` });

  const voice = typeof body.voice === "string" && VOICE_RE.test(body.voice) ? body.voice : DEFAULT_VOICE;
  const style = typeof body.style === "string" && STYLE_RE.test(body.style) ? body.style : "";
  const rate = typeof body.rate === "string" && PROSODY_RE.test(body.rate) ? body.rate : "+0%";
  const pitch = typeof body.pitch === "string" && PROSODY_RE.test(body.pitch) ? body.pitch : "+0%";

  let azure: Response;
  try {
    azure = await fetch(`https://${region}.tts.speech.microsoft.com/cognitiveservices/v1`, {
      method: "POST",
      headers: {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "cross-tts",
      },
      body: buildSsml(text, voice, style, rate, pitch),
    });
  } catch (e) {
    console.error("azure tts fetch failed", e instanceof Error ? e.message : e);
    return json(502, { error: "Azure Speech に接続できない（リージョン名を確認）" });
  }

  if (!azure.ok) {
    const detail = (await azure.text().catch(() => "")).slice(0, 300);
    console.error("azure tts error", azure.status, detail);
    return json(502, { error: `Azure Speech ${azure.status}`, detail });
  }
  return new Response(azure.body, {
    headers: { ...CORS, "Content-Type": "audio/mpeg", "Cache-Control": "no-store" },
  });
});
