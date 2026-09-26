// /chat — Claude Messages API をストリーミング中継する（SSE）
//
// 入力（POST JSON）:
//   { messages: [{role:"user"|"assistant", content:string}, ...], model?: "default"|"upper" }
// 出力（text/event-stream、各行 `data: {...}`）:
//   {type:"start", model}
//   {type:"delta", text}
//   {type:"done", model, stop_reason, usage}
//   {type:"error", message}
import Anthropic from "@anthropic-ai/sdk";
import { KNOWLEDGE, PERSONA } from "./prompt.ts";
import { CORS, gate, json } from "../_shared/auth.ts";

const MODEL_DEFAULT = Deno.env.get("MODEL_DEFAULT") ?? "claude-haiku-4-5-20251001";
const MODEL_UPPER = Deno.env.get("MODEL_UPPER") ?? "claude-sonnet-5";
const UPGRADE_KEYWORDS = ["分析", "事業", "計算", "比較"];
const MAX_MESSAGES = 20; // 直近10往復

// system prompt は固定文字列（キャッシュのプレフィックスを崩さないため、時刻等を入れない）
const SYSTEM_PROMPT = [
  PERSONA.trim(),
  KNOWLEDGE.trim() ? `# Crossactorの事業情報\n\n${KNOWLEDGE.trim()}` : "",
  [
    "# 出力ルール",
    "- 返答はそのまま音声合成で読み上げられる。話し言葉で書く",
    "- 1回の返答は1〜3文。長くても3文で切る",
    "- 記号、箇条書き、見出し、URL、絵文字、英略語を使わない",
    "- 数字は読み上げやすく丸める",
  ].join("\n"),
].filter(Boolean).join("\n\n---\n\n");

type ChatMessage = { role: "user" | "assistant"; content: string };

function normalizeMessages(raw: unknown): ChatMessage[] | null {
  if (!Array.isArray(raw)) return null;
  const out: ChatMessage[] = [];
  for (const m of raw) {
    if (!m || (m.role !== "user" && m.role !== "assistant")) return null;
    const content = typeof m.content === "string" ? m.content.trim() : "";
    if (!content) continue;
    // 同一ロールの連続は結合（APIは交互必須）
    const last = out[out.length - 1];
    if (last && last.role === m.role) last.content += "\n" + content;
    else out.push({ role: m.role, content });
  }
  // 先頭は user、末尾も user であること
  while (out.length && out[0].role !== "user") out.shift();
  if (!out.length || out[out.length - 1].role !== "user") return null;
  // 直近 MAX_MESSAGES に切り詰め（先頭が user になる位置で切る）
  let trimmed = out.slice(-MAX_MESSAGES);
  while (trimmed.length && trimmed[0].role !== "user") trimmed = trimmed.slice(1);
  return trimmed;
}

function pickModel(requested: unknown, lastUserText: string): string {
  if (requested === "upper") return MODEL_UPPER;
  if (requested === "default") return MODEL_DEFAULT;
  return UPGRADE_KEYWORDS.some((k) => lastUserText.includes(k)) ? MODEL_UPPER : MODEL_DEFAULT;
}

Deno.serve(async (req) => {
  const blocked = gate(req);
  if (blocked) return blocked;

  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) return json(500, { error: "ANTHROPIC_API_KEY が Secrets に未設定" });

  let body: { messages?: unknown; model?: unknown };
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "JSON body が必要" });
  }
  const messages = normalizeMessages(body.messages);
  if (!messages) return json(400, { error: "messages が不正（末尾は user の発話であること）" });

  const model = pickModel(body.model, messages[messages.length - 1].content);
  const client = new Anthropic({ apiKey });
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (obj: unknown) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      try {
        send({ type: "start", model });

        const params: Anthropic.MessageStreamParams = {
          model,
          // 返答は1〜3文。thinkingを使うモデルはその分も含むため余裕を持たせる
          max_tokens: 1024,
          system: [
            { type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } },
          ],
          messages,
        };
        if (!model.includes("haiku")) {
          // 音声対話は遅延優先。上位モデルは思考オフ・低エフォートで短く返す
          params.thinking = { type: "disabled" };
          params.output_config = { effort: "low" };
        }

        const s = client.messages.stream(params);
        s.on("text", (text) => send({ type: "delta", text }));
        const final = await s.finalMessage();

        send({
          type: "done",
          model,
          stop_reason: final.stop_reason,
          usage: {
            input: final.usage.input_tokens,
            output: final.usage.output_tokens,
            cache_read: final.usage.cache_read_input_tokens ?? 0,
            cache_write: final.usage.cache_creation_input_tokens ?? 0,
          },
        });
      } catch (e) {
        const message = e instanceof Anthropic.APIError
          ? `Claude API ${e.status}: ${e.message}`
          : e instanceof Error ? e.message : String(e);
        console.error("chat error:", message);
        send({ type: "error", message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      ...CORS,
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
});
