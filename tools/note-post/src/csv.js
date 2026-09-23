import fs from 'node:fs';

// 依存を増やさない最小CSV（ダブルクォート・カンマ・改行対応）
export function parseCsv(text) {
  const rows = [];
  let row = [], field = '', q = false;
  text = text.replace(/^﻿/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') q = false;
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); rows.push(row); row = []; field = '';
    } else field += c;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.some((v) => v.trim() !== ''));
}

const esc = (v) => (/[",\r\n]/.test(v ?? '') ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? ''));
export const toCsvLine = (arr) => arr.map(esc).join(',');

export function readTable(file) {
  if (!fs.existsSync(file)) return { header: [], rows: [] };
  const [header = [], ...data] = parseCsv(fs.readFileSync(file, 'utf8'));
  const rows = data.map((r) => Object.fromEntries(header.map((h, i) => [h, r[i] ?? ''])));
  return { header, rows };
}

export function writeTable(file, header, rows) {
  const lines = [toCsvLine(header), ...rows.map((r) => toCsvLine(header.map((h) => r[h])))];
  fs.writeFileSync(file, lines.join('\n') + '\n');
}

export function appendRow(file, header, obj) {
  if (!fs.existsSync(file)) fs.writeFileSync(file, toCsvLine(header) + '\n');
  fs.appendFileSync(file, toCsvLine(header.map((h) => obj[h])) + '\n');
}
