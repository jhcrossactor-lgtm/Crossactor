import fs from 'node:fs';
import OpenAI from 'openai';
import { config } from './config.js';

// 記事中の画像マーカー: <!-- image: 英語プロンプト | alt: 日本語説明 -->
const MARKER = /^<!--\s*image:\s*(.+?)\s*\|\s*alt:\s*(.+?)\s*-->$/gm;

export function extractImageMarkers(body) {
  return [...body.matchAll(MARKER)].map((m) => ({ marker: m[0], prompt: m[1], alt: m[2] }));
}

export const stripImageMarkers = (body) => body.replace(MARKER, '').replace(/\n{3,}/g, '\n\n');

// 1x1 PNG（モック用）
const MOCK_PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

const STYLE = 'Flat, clean editorial illustration for a Japanese business blog. No text, no letters, no logos, no real people or recognizable faces.';

/**
 * マーカーごとに画像を生成して保存する。1枚失敗しても他は続行し、失敗分はマーカーごと本文から外す。
 * 戻り値: { body, images: [{marker, alt, file}], errors: [string] }
 */
export async function generateImages(body, filePrefix) {
  const markers = extractImageMarkers(body).slice(0, config.imageCount);
  const extra = extractImageMarkers(body).slice(config.imageCount);
  for (const m of extra) body = body.replace(m.marker, '');
  if (!markers.length) return { body, images: [], errors: [] };

  if (!config.mockLlm && !process.env.OPENAI_API_KEY) {
    return { body: stripImageMarkers(body), images: [], errors: ['OPENAI_API_KEY未設定のため画像なしで続行'] };
  }

  const client = config.mockLlm ? null : new OpenAI();
  const images = [], errors = [];
  for (const [i, m] of markers.entries()) {
    const file = `${filePrefix}-img${i + 1}.png`;
    try {
      let b64 = MOCK_PNG;
      if (client) {
        const res = await client.images.generate({
          model: config.imageModel,
          prompt: `${m.prompt}\n\n${STYLE}`,
          size: '1536x1024',
          quality: config.imageQuality,
          n: 1,
        });
        b64 = res.data?.[0]?.b64_json;
        if (!b64) throw new Error('画像データが返らなかった');
      }
      fs.writeFileSync(file, Buffer.from(b64, 'base64'));
      images.push({ marker: m.marker, alt: m.alt, file });
    } catch (e) {
      errors.push(`画像${i + 1}生成失敗（${m.alt}）: ${e.message}`);
      body = body.replace(m.marker, '');
    }
  }
  return { body, images, errors };
}
