// /tts — Azure Speech（REST）で1文を mp3 にして返す
//
// 入力（POST JSON）: { text: string, voice?: string, style?: string, rate?: string, pitch?: string }
// 出力: audio/mpeg（24kHz 48kbps mono）
// 一覧: { list: true } → 日本語を話せる声の一覧（JSON）
import { gate, json, CORS } from "../_shared/auth.ts";

const MAX_CHARS = 400;
const DEFAULT_VOICE = Deno.env.get("TTS_VOICE") ?? "ja-JP-KeitaNeural";

function xmlEscape(s: string): string {
  return s.replace(/[<>&'"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c]!));
}
const VOICE_RE = /^[A-Za-z]{2}-[A-Za-z]{2,4}-[A-Za-z0-9]+(:[A-Za-z0-9]+)?Neural$/;   // 例: ja-JP-NanamiNeural, en-US-Ava:DragonHDLatestNeural

// 日本語を話せる声の一覧（Azure の voices/list を取得し、ja-JP ネイティブ＋多言語対応をフィルタ）。10分キャッシュ
type VoiceInfo = { name: string; gender: string; locale: string; localeName: string; styles: string[]; native: boolean; type: string };
let voiceCache: { at: number; list: VoiceInfo[] } | null = null;
async function listJapaneseVoices(key: string, region: string): Promise<VoiceInfo[]> {
  if (voiceCache && Date.now() - voiceCache.at < 10 * 60 * 1000) return voiceCache.list;
  const r = await fetch(`https://${region}.tts.speech.microsoft.com/cognitiveservices/voices/list`, {
    headers: { "Ocp-Apim-Subscription-Key": key },
  });
  if (!r.ok) throw new Error(`voices/list HTTP ${r.status}`);
  // deno-lint-ignore no-explicit-any
  const all: any[] = await r.json();
  const list: VoiceInfo[] = all
    .filter((v) => v.Locale === "ja-JP" || (Array.isArray(v.SecondaryLocaleList) && v.SecondaryLocaleList.includes("ja-JP")))
    .map((v) => ({
      name: v.ShortName, gender: v.Gender, locale: v.Locale, localeName: v.LocaleName,
      styles: Array.isArray(v.StyleList) ? v.StyleList : [], native: v.Locale === "ja-JP", type: v.VoiceType,
    }))
    .sort((a, b) => Number(b.native) - Number(a.native) || a.name.localeCompare(b.name));
  voiceCache = { at: Date.now(), list };
  return list;
}
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
  // ウォームアップ：画面起動時に呼ばれ、関数のコールドスタートを先に済ませる
  if (req.headers.get("x-cross-warm") === "1") return json(200, { ok: true, warm: true });

  const key = Deno.env.get("AZURE_SPEECH_KEY");
  const region = Deno.env.get("AZURE_SPEECH_REGION");
  if (!key || !region) return json(503, { error: "AZURE_SPEECH_KEY / AZURE_SPEECH_REGION が Secrets に未設定", code: "tts_unconfigured" });

  let body: { text?: unknown; voice?: unknown; style?: unknown; rate?: unknown; pitch?: unknown; list?: unknown };
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "JSON body が必要" });
  }
  if (body.list === true) {
    try {
      return json(200, { voices: await listJapaneseVoices(key, region) });
    } catch (e) {
      return json(502, { error: e instanceof Error ? e.message : String(e) });
    }
  }
  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!text) return json(400, { error: "text が空" });
  if (text.length > MAX_CHARS) return json(400, { error: `text が長すぎる（最大${MAX_CHARS}文字）` });

  const voice = typeof body.voice === "string" && VOICE_RE.test(body.voice) ? body.voice : DEFAULT_VOICE;
  const style = typeof body.style === "string" && STYLE_RE.test(body.style) ? body.style : "";
  const rate = typeof body.rate === "string" && PROSODY_RE.test(body.rate) ? body.rate : "+0%";
  const pitch = typeof body.pitch === "string" && PROSODY_RE.test(body.pitch) ? body.pitch : "+0%";

  const synth = (ssml: string) =>
    fetch(`https://${region}.tts.speech.microsoft.com/cognitiveservices/v1`, {
      method: "POST",
      headers: {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "cross-tts",
      },
      body: ssml,
    });

  let azure: Response;
  try {
    azure = await synth(buildSsml(text, voice, style, rate, pitch));
    // スタイル非対応の声は 400 になることがある → スタイル無しで一度だけ再試行
    if (!azure.ok && style) {
      await azure.body?.cancel();
      azure = await synth(buildSsml(text, voice, "", rate, pitch));
    }
  } catch (e) {
    console.error("azure tts fetch failed", e instanceof Error ? e.message : e);
    return json(502, { error: "Azure Speech に接続できない（リージョン名を確認）" });
  }

  if (!azure.ok) {
    const detail = (await azure.text().catch(() => "")).slice(0, 300);
    console.error("azure tts error", azure.status, voice, detail);
    return json(502, { error: `Azure Speech ${azure.status}`, detail });
  }
  return new Response(azure.body, {
    headers: { ...CORS, "Content-Type": "audio/mpeg", "Cache-Control": "no-store" },
  });
});
