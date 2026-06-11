"""PDFから敷地情報を抽出する。テキスト抽出 + Claude Vision で構造化する。"""
import re
import json
import os
import fitz
import anthropic
import base64
from pathlib import Path

from config import CLAUDE_MODEL


def _extract_text_and_images(pdf_path: Path) -> tuple[str, list[bytes]]:
    doc = fitz.open(str(pdf_path))
    full_text, images = [], []
    for page in doc:
        full_text.append(page.get_text())
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    doc.close()
    return "\n".join(full_text), images


def _parse_with_claude(text: str, images: list[bytes], parcel_hint: str = "") -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    image_content = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode()
        image_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })

    hint = f"このPDFには {parcel_hint} の複数筆が含まれています。それぞれ個別に抽出してください。" if parcel_hint else ""

    prompt = f"""以下は複数ページのPDF（公図・測量図・謄本・都市計画図など）です。全ページを確認し、
含まれるすべての地番（筆）の情報を漏れなく抽出してください。{hint}

【都市計画図・用途地域図がある場合】
- 色分けされた都市計画図から用途地域・建蔽率・容積率・防火地域を読み取ること
- 図中の凡例や「市化:1住:80:200:準防」のような略記も解読すること
- 用途地域の正式名称に変換すること（例: 1住→第一種住居地域、2住→第二種住居地域、1低→第一種低層住居専用地域）

必ず以下のJSON形式で返してください（コードブロック不要、JSONのみ）:
{{
  "所在地": "都道府県市区町村〇〇丁目",
  "用途地域": "第一種住居地域 など正式名称",
  "建蔽率": 0.80,
  "容積率": 2.00,
  "防火地域": "準防火地域 または 防火地域 または null",
  "前面道路_幅員_m": null,
  "前面道路_方位": "南 など",
  "高度地区": null,
  "筆": [
    {{
      "地番": "98-2",
      "敷地面積_m2": 500.0,
      "境界座標": [[y1,x1],[y2,x2],...]
    }}
  ],
  "備考": ""
}}

ルール:
- 建蔽率・容積率は小数で（80%なら0.80）
- 境界座標は測量図から読み取れる場合のみ。座標順は【Y（北方向）,X（東方向）】の順で記入
- 前面道路幅員は図面・謄本に記載がある場合のみ数値で
- 不明な項目はnull

テキスト内容:
{text[:3000]}"""

    content = image_content + [{"type": "text", "text": prompt}]
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text
    match = re.search(r"\{[\s\S]+\}", raw)
    if match:
        return json.loads(match.group())
    return {}


def parse_site_pdf(pdf_path: str | Path, parcel_hint: str = "") -> dict:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    text, images = _extract_text_and_images(pdf_path)
    return _parse_with_claude(text, images, parcel_hint)
