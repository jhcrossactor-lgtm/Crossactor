// 共通：CORS と認可
// verify_jwt = false のため、各関数がここで自前に照合する。
// 1) apikey ヘッダがこのプロジェクトの publishable キー（または legacy anon）と一致すること
// 2) Secrets に CROSS_ACCESS_KEY があれば、x-cross-key ヘッダがそれと一致すること（合言葉。任意）

export const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-cross-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

function allowedApiKeys(): Set<string> {
  const keys = new Set<string>();
  try {
    const pub = Deno.env.get("SUPABASE_PUBLISHABLE_KEYS");
    if (pub) for (const v of Object.values(JSON.parse(pub))) if (typeof v === "string") keys.add(v);
  } catch { /* 形式不正は無視 */ }
  const legacy = Deno.env.get("SUPABASE_ANON_KEY");
  if (legacy) keys.add(legacy);
  return keys;
}

/** 認可NGなら理由文字列、OKなら null */
export function authorize(req: Request): string | null {
  const keys = allowedApiKeys();
  const apikey = req.headers.get("apikey") ?? "";
  if (keys.size === 0) return "サーバー側に publishable キーが見つからない（SUPABASE_PUBLISHABLE_KEYS 未注入）";
  if (!apikey || !keys.has(apikey)) return "apikey が不正";
  const access = Deno.env.get("CROSS_ACCESS_KEY");
  if (access && req.headers.get("x-cross-key") !== access) return "合言葉が不正";
  return null;
}

/** OPTIONS / メソッド / 認可をまとめて処理。通過なら null、弾くなら Response */
export function gate(req: Request): Response | null {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });
  const denied = authorize(req);
  if (denied) return json(401, { error: denied });
  return null;
}
