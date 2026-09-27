// Notion 収益管理DB（売上DB / LINEスタンプ売上DB）を読んで、音声報告用の要約を作る
//
// Secrets:
//   NOTION_TOKEN     … Notion のインテグレーション・シークレット（対象DBを連携に共有しておく）
//   NOTION_SALES_DS  … 売上DB のデータソースID（UUID）
//   NOTION_LINE_DS   … LINEスタンプ売上DB のデータソースID（UUID。任意）
//
// 返り値 summary.text は Claude の system に渡す文章、summary.panel は画面の情報パネル用。

type Row = Record<string, unknown>;

export type RevenueSummary = {
  text: string;
  panel: { title: string; rows: { label: string; value: string }[] };
  fetchedAt: string;
};

const NOTION_VERSION_NEW = "2025-09-03";
const NOTION_VERSION_OLD = "2022-06-28";

async function queryDataSource(token: string, dsId: string): Promise<Row[]> {
  const headers = { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" };
  const out: Row[] = [];
  // 新API（data_sources）→ ダメなら旧API（databases）にフォールバック
  const attempts: Array<[string, string]> = [
    [`https://api.notion.com/v1/data_sources/${dsId}/query`, NOTION_VERSION_NEW],
    [`https://api.notion.com/v1/databases/${dsId}/query`, NOTION_VERSION_OLD],
  ];
  let lastErr = "";
  for (const [url, ver] of attempts) {
    let cursor: string | undefined;
    out.length = 0;
    let ok = true;
    do {
      const r = await fetch(url, {
        method: "POST",
        headers: { ...headers, "Notion-Version": ver },
        body: JSON.stringify({ page_size: 100, ...(cursor ? { start_cursor: cursor } : {}) }),
      });
      if (!r.ok) { lastErr = `${r.status} ${(await r.text()).slice(0, 200)}`; ok = false; break; }
      const j = await r.json();
      for (const p of j.results ?? []) out.push(p.properties ?? {});
      cursor = j.has_more ? j.next_cursor : undefined;
    } while (cursor);
    if (ok) return out;
  }
  throw new Error(`Notion query failed: ${lastErr}`);
}

// ---- プロパティ取り出し ----
// deno-lint-ignore no-explicit-any
const P = (row: Row, name: string): any => row[name];
function num(row: Row, name: string): number | null { const p = P(row, name); return typeof p?.number === "number" ? p.number : null; }
function sel(row: Row, name: string): string { return P(row, name)?.select?.name ?? ""; }
function date(row: Row, name: string): string { return P(row, name)?.date?.start ?? ""; }
function text(row: Row, name: string): string {
  const p = P(row, name);
  const arr = p?.title ?? p?.rich_text ?? [];
  return Array.isArray(arr) ? arr.map((t) => t?.plain_text ?? "").join("") : "";
}
const yen = (n: number) => `¥${Math.round(n).toLocaleString("ja-JP")}`;
const ym = (d: string) => d.slice(0, 7);

export async function fetchRevenueSummary(): Promise<RevenueSummary | null> {
  const token = Deno.env.get("NOTION_TOKEN");
  const salesDs = Deno.env.get("NOTION_SALES_DS");
  const lineDs = Deno.env.get("NOTION_LINE_DS");
  if (!token || !salesDs) return null;

  const now = new Date();
  const thisMonth = now.toISOString().slice(0, 7);
  const thisYear = now.toISOString().slice(0, 4);
  const today = now.toISOString().slice(0, 10);

  const sales = await queryDataSource(token, salesDs);
  const items = sales.map((r) => ({
    name: text(r, "案件名"), client: sel(r, "クライアント"), kind: sel(r, "種別"), status: sel(r, "ステータス"),
    billed: date(r, "請求日"), paid: date(r, "入金日"), amount: num(r, "金額（税抜）") ?? 0, note: text(r, "備考"),
  }));

  // 売上の定義：請求額＝売上（入金は追わない）。請求日ベースで集計。見積は「見込み」として別枠
  const billedRows = items.filter((i) => i.status !== "見積" && i.billed);
  const prevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().slice(0, 7);
  const sumOf = (rows: typeof items) => rows.reduce((s, i) => s + i.amount, 0);
  const monthRows = billedRows.filter((i) => ym(i.billed) === thisMonth);
  const prevRows = billedRows.filter((i) => ym(i.billed) === prevMonth);
  const ytdRows = billedRows.filter((i) => i.billed.slice(0, 4) === thisYear);
  const monthTotal = sumOf(monthRows), prevTotal = sumOf(prevRows), ytd = sumOf(ytdRows), allTime = sumOf(billedRows);
  const estimates = items.filter((i) => i.status === "見積");
  const estTotal = sumOf(estimates);
  const byClient = new Map<string, number>();
  for (const i of ytdRows) byClient.set(i.client || "その他", (byClient.get(i.client || "その他") ?? 0) + i.amount);
  const byKind = new Map<string, number>();
  for (const i of ytdRows) byKind.set(i.kind || "その他", (byKind.get(i.kind || "その他") ?? 0) + i.amount);
  const flagged = items.filter((i) => /要確認/.test(i.note));
  const noDate = items.filter((i) => i.status !== "見積" && !i.billed);

  let lineText = "";
  const lineRows: { label: string; value: string }[] = [];
  if (lineDs) {
    try {
      const line = await queryDataSource(token, lineDs);
      const lr = line.map((r) => ({
        item: sel(r, "アイテム"), month: ym(date(r, "対象月")), kind: sel(r, "区分"),
        sold: num(r, "販売数") ?? 0, sent: num(r, "送信数") ?? 0, amount: num(r, "売上（分配額）") ?? 0,
      })).filter((x) => x.month);
      if (lr.length) {
        const latest = lr.map((x) => x.month).sort().at(-1)!;
        const rows = lr.filter((x) => x.month === latest);
        const amt = rows.reduce((s, x) => s + x.amount, 0);
        const sold = rows.reduce((s, x) => s + x.sold, 0);
        lineText = `LINEスタンプは直近の対象月 ${latest} が販売数 ${sold}、分配額 ${yen(amt)}（${rows[0].kind}）。`;
        lineRows.push({ label: `LINEスタンプ ${latest}`, value: `${yen(amt)} / ${sold}個` });
      } else {
        lineText = "LINEスタンプ売上DBはまだ0行。";
      }
    } catch (e) {
      lineText = `LINEスタンプDBは読めなかった（${e instanceof Error ? e.message : e}）。`;
    }
  }

  const fmtList = (m: Map<string, number>) => [...m.entries()].sort((a, b) => b[1] - a[1]).map(([c, v]) => `${c} ${yen(v)}`).join("、");
  const lines = [
    `【Notion 収益管理DB 要約（${today} 時点、金額は税抜、請求額＝売上、請求日ベース）】`,
    `売上DBの登録件数: ${items.length}件。`,
    `今月（${thisMonth}）の売上: ${monthRows.length}件 合計 ${yen(monthTotal)}。` +
      (monthRows.length ? " 内訳: " + monthRows.map((i) => `${i.name}（${i.client}／${i.kind}／${yen(i.amount)}）`).join("、") + "。" : ""),
    `先月（${prevMonth}）の売上: ${prevRows.length}件 合計 ${yen(prevTotal)}。`,
    `年初来（${thisYear}年）: ${yen(ytd)}。累計: ${yen(allTime)}。`,
    byClient.size ? `年初来のクライアント別: ${fmtList(byClient)}。` : "",
    byKind.size ? `年初来の種別: ${fmtList(byKind)}。` : "",
    `見積中（見込み）: ${estimates.length}件 合計 ${yen(estTotal)}。` +
      (estimates.length ? " " + estimates.map((i) => `${i.name}（${i.client}／${yen(i.amount)}）`).join("、") + "。" : ""),
    noDate.length ? `請求日が空の案件（集計から漏れている）: ${noDate.map((i) => i.name).join("、")}。` : "",
    flagged.length ? `備考に「要確認」がある案件: ${flagged.map((i) => `${i.name}（${i.note.slice(0, 40)}）`).join("、")}。` : "",
    lineText,
    "報告のときは、今月の売上を先に、次に先月比や年初来を短く。金額は「約」で丸めて言う。入金や未入金の話はしない。要確認があれば触れる。最大5文まで。",
  ].filter(Boolean);

  const panelRows = [
    { label: `今月の売上（${thisMonth}）`, value: `${yen(monthTotal)} / ${monthRows.length}件` },
    { label: `先月（${prevMonth}）`, value: `${yen(prevTotal)} / ${prevRows.length}件` },
    { label: `年初来（${thisYear}年）`, value: yen(ytd) },
    ...[...byClient.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([c, v]) => ({ label: `　${c}`, value: yen(v) })),
    { label: "累計", value: yen(allTime) },
    { label: "見積中（見込み）", value: `${yen(estTotal)} / ${estimates.length}件` },
    ...lineRows,
  ];

  return { text: lines.join("\n"), panel: { title: "収益サマリー", rows: panelRows }, fetchedAt: now.toISOString() };
}

export const REVENUE_KEYWORDS = [
  "売上", "売り上げ", "売上げ", "うりあげ", "収益", "収入", "入金", "請求", "報告", "利益", "儲か", "もうか",
  "稼", "未入金", "見積", "売れ", "お金の状況", "数字どう", "今月の数字", "業績",
];
export function wantsRevenue(text: string): boolean {
  const t = text.replace(/\s/g, "");
  return REVENUE_KEYWORDS.some((k) => t.includes(k));
}
