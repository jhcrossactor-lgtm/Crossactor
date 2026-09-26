"""総譜 PDF の各ページを「向きを揃え、曲がった五線をまっすぐに直した」画像にする。

- 向き: 五線が横になる方向に回し、音部記号のある側（インクが濃い側）が左になるよう 180° を決める
- 曲がり: 各五線を横方向に追跡して曲線を取り、その曲線が水平になるように画像を縦方向に伸縮する
  （本のとじ目側で五線が湾曲したスキャン向け。五線が繋がっていれば追える）

使い方: py prepare_pages.py <総譜.pdf> --out <出力フォルダ> [--staves 10]
出力:   <出力フォルダ>/pNN.png（整えたページ）, _contact.png（確認用一覧）, _report.txt
"""
import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

BAND = 24  # 五線追跡の横方向の刻み（px）


# ---------------------------------------------------------------- 入力

def page_images(pdf: Path):
    """PDF の各ページに埋め込まれたスキャン画像を元の解像度のまま取り出す。"""
    import pymupdf

    with pymupdf.open(pdf) as doc:
        for page in doc:
            imgs = page.get_images()
            if len(imgs) == 1:
                yield Image.open(io.BytesIO(doc.extract_image(imgs[0][0])["image"])).convert("L")
            else:
                pix = page.get_pixmap(dpi=200, alpha=False)
                yield Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")


def flatten(im: Image.Image) -> np.ndarray:
    """背景の明暗ムラを除去する（大きくぼかした背景で割る）。"""
    bg = im.filter(ImageFilter.GaussianBlur(radius=25))
    a = np.asarray(im, np.float32)
    b = np.maximum(np.asarray(bg, np.float32), 1.0)
    return np.clip(a / b * 255.0, 0, 255)


# ---------------------------------------------------------------- 五線検出（1本の縦帯の中で）

def row_signal(a: np.ndarray, x0: int, x1: int) -> np.ndarray:
    """帯 [x0,x1) の行ごとの暗さから背景成分を引いた信号。五線の行が山になる。"""
    rowdark = 255.0 - a[:, x0:x1].mean(axis=1)
    return rowdark - np.convolve(rowdark, np.ones(31) / 31, mode="same")


def find_staves(sig: np.ndarray, max_gap: int = 30):
    """信号の山から五線（等間隔5本）を拾う → [(上端y, 下端y, 線間隔)]"""
    thr = sig.std() * 0.9
    peaks = [y for y in range(1, len(sig) - 1) if sig[y] > thr and sig[y] >= sig[y - 1] and sig[y] > sig[y + 1]]
    staves, i = [], 0
    while i <= len(peaks) - 5:
        grp = peaks[i:i + 5]
        gaps = [grp[k + 1] - grp[k] for k in range(4)]
        if all(2 <= g <= max_gap for g in gaps) and max(gaps) - min(gaps) <= max(3, min(gaps) // 4):
            staves.append((grp[0], grp[-1], (grp[-1] - grp[0]) / 4.0))
            i += 5
        else:
            i += 1
    return staves


# ---------------------------------------------------------------- 向き

def count_staves(a: np.ndarray) -> int:
    """中央の縦帯で見つかる五線の段数。五線が縦に走っている向きだとほぼ 0 になる。"""
    h, w = a.shape
    return len(find_staves(row_signal(a, int(w * 0.45), int(w * 0.55))))


def make_horizontal(a: np.ndarray):
    """五線が横になる向きに回す（0 か 90°）。"""
    r = np.rot90(a)
    return (r, 90) if count_staves(r) > count_staves(a) else (a, 0)


def staff_x_range(a: np.ndarray, top: int, bot: int):
    """五線が引かれている横範囲（5本のうち4本以上が暗い列の最長連続区間）。"""
    sp = (bot - top) / 4.0
    # 5本それぞれについて、線の位置 ±1 行のどこかが暗ければ「その列に線がある」とみなす
    # （曲がり補正の補間で線が薄くなることがあるので、しきい値は緩め）
    present = []
    for k5 in range(5):
        r = int(round(top + k5 * sp))
        present.append(a[max(0, r - 1):r + 2, :].min(axis=0) < 200)
    cnt = np.sum(present, axis=0)
    dark = (cnt >= 3).astype(np.uint8)[None, :]
    # 小さな途切れ（かすれ・記号の重なり）は埋める
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (int(sp * 4) | 1, 1))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, k)[0].astype(bool)
    dark = np.append(dark, False)
    best, start = (0, 0), None
    for x, d in enumerate(dark):
        if d and start is None:
            start = x
        elif not d and start is not None:
            if x - start > best[1] - best[0]:
                best = (start, x)
            start = None
    return best


def clef_side_is_left(a: np.ndarray, staves) -> bool:
    """各五線の始端付近（音部記号）と終端付近のインク量を比べる。音部記号側の方が濃い。"""
    left = right = 0.0
    for top, bot, sp in staves:
        x0, x1 = staff_x_range(a, top, bot)
        if x1 - x0 < sp * 40:
            continue
        span = int(sp * 4)
        y0, y1 = max(0, int(top - sp)), int(bot + sp)
        left += float((255 - a[y0:y1, x0:x0 + span]).mean())
        right += float((255 - a[y0:y1, x1 - span:x1]).mean())
    return left >= right


# ---------------------------------------------------------------- 曲がり補正

def track_staff(a: np.ndarray, top: int, sp: float, xc: int):
    """5本の線を1組（くし型）として左右に追跡し、帯ごとの上端 y を返す（見失った帯は None）。"""
    h, w = a.shape
    dark = 255.0 - a
    offsets = [int(round(k * sp)) for k in range(5)]
    tol = max(3, int(sp * 0.8))
    nb = w // BAND
    ys = [None] * nb

    def score(x0, y):
        rows = [y + o for o in offsets]
        if rows[0] < 0 or rows[-1] >= h:
            return -1
        return float(sum(dark[r, x0:x0 + BAND].mean() for r in rows)) / 5

    def run(j0, step):
        prev, prev2, miss, good = None, None, 0, []
        for j in range(j0, nb if step > 0 else -1, step):
            if prev is None:
                pred = top
            else:
                pred = prev + (prev - prev2 if prev2 is not None else 0)
            # 予測位置から離れた候補は減点し、連桁など別の横線に飛び移りにくくする
            best = max(range(pred - tol, pred + tol + 1),
                       key=lambda y: score(j * BAND, y) - 3.0 * abs(y - pred))
            s = score(j * BAND, best)
            # 線がある帯なら5本の平均暗さがそれなりにある。急に薄くなったら見失い、空白が続けば段の終わり
            typical = float(np.median(good)) if good else s
            if s < 40 or s < typical * 0.5:
                miss += 1
                if miss >= 3:
                    break
                prev2, prev = prev, (prev if prev is not None else top)
                continue
            miss = 0
            ys[j] = best
            good.append(s)
            prev2, prev = prev, best

    jc = xc // BAND
    run(jc, 1)
    run(jc, -1)
    # 見失った帯を線形補間で埋める（両端の外側は端の値で延長）
    idx = [j for j, y in enumerate(ys) if y is not None]
    if len(idx) < 3:
        return None
    j_all = np.arange(nb)
    filled = np.interp(j_all, idx, [ys[j] for j in idx])
    # 端の外側は外挿ではなく最寄りの値（np.interp の既定）。追跡できた範囲も返す
    return filled, (idx[0], idx[-1])


def seed_staves(a: np.ndarray):
    """複数の縦帯で五線を探し、追跡の起点 [(上端y, 下端y, 線間隔, 起点x)] を集める。
    曲がったページでは1本の帯だけだと取りこぼすため、帯ごとの結果を y で重複除去して合わせる。"""
    h, w = a.shape
    dark = 255.0 - a[:, int(w * 0.25):int(w * 0.95)]

    def strength(top, sp):
        rows = [min(h - 1, int(round(top + k * sp))) for k in range(5)]
        return float(np.mean([dark[r].mean() for r in rows]))

    found = []  # [top, bot, sp, xc, strength]
    for fx in (0.5, 0.4, 0.6, 0.3, 0.7):
        xc = int(w * fx)
        for top, bot, sp in find_staves(row_signal(a, xc - int(w * 0.05), xc + int(w * 0.05))):
            s = strength(top, sp)
            # 段どうしは五線の高さ＋1間隔以上離れる。近いものは同じ段の重複か偽検出なので、線の濃い方だけ残す
            near = [f for f in found if abs(top - f[0]) < sp * 5]
            if near:
                if s > max(f[4] for f in near):
                    for f in near:
                        found.remove(f)
                    found.append([top, bot, sp, xc, s])
            else:
                found.append([top, bot, sp, xc, s])
    return sorted((t, b, sp, xc) for t, b, sp, xc, _ in found)


def dewarp(a: np.ndarray, seeds, xc: int):
    """見つけた各五線を追跡し、曲線が水平になるように縦方向にずらした画像を返す。"""
    h, w = a.shape
    nb = w // BAND
    rows_y, rows_d = [], []
    tracks = []
    for top, bot, sp, x_seed in seeds:
        r = track_staff(a, top, sp, x_seed)
        if r is None:
            continue
        curve, span = r
        d = curve - curve[xc // BAND]           # 中央を基準にしたずれ
        d = np.convolve(np.pad(d, 2, mode="edge"), np.ones(5) / 5, mode="valid")  # 軽く平滑化
        rows_y.append((top + bot) / 2)
        rows_d.append(d)
        tracks.append((top, bot, sp, span))
    if not rows_d:
        return a, tracks
    rows_y = np.array(rows_y)
    D = np.array(rows_d)                          # (段数, 帯数)
    # 隣の段と大きく違うずれは追跡の外れとみなし、隣の段の値（中央値）に置き換える
    if len(D) >= 3:
        sp_med = float(np.median([t[2] for t in tracks]))
        neigh = np.stack([np.roll(D, 1, axis=0), D, np.roll(D, -1, axis=0)])
        neigh[0, 0], neigh[2, -1] = D[0], D[-1]
        med = np.median(neigh, axis=0)
        # ページ端は曲がりが隣と違って当然なので、置き換えるのは大きく外れた場合だけ
        bad = np.abs(D - med) > sp_med * 2.5
        D = np.where(bad, med, D)
    # 段と段の間は線形補間、外側は最寄りの段のずれをそのまま使う
    band_x = (np.arange(nb) + 0.5) * BAND
    field = np.empty((h, nb), np.float32)
    for j in range(nb):
        field[:, j] = np.interp(np.arange(h), rows_y, D[:, j])
    full = cv2.resize(field, (w, h), interpolation=cv2.INTER_LINEAR)
    map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    map_y = (np.arange(h, dtype=np.float32)[:, None] + full).astype(np.float32)
    out = cv2.remap(a.astype(np.uint8), map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    return out.astype(np.float32), tracks


# ---------------------------------------------------------------- メイン

def process_page(im: Image.Image):
    a = flatten(im)
    a, rot = make_horizontal(a)
    h, w = a.shape
    seeds = seed_staves(a)
    out, tracks = dewarp(a, seeds, w // 2)
    # 1回目で取りこぼした段や残った曲がりを、まっすぐになった画像でもう一度追跡して直す
    out, _ = dewarp(out, seed_staves(out), w // 2)
    after = [(t, b, sp) for t, b, sp, _ in seed_staves(out)]
    # まっすぐになった五線で音部記号の側を調べ、右にあれば 180° 回す
    if after and not clef_side_is_left(out, after):
        out, rot = np.ascontiguousarray(np.rot90(out, 2)), rot + 180
        after = [(t, b, sp) for t, b, sp, _ in seed_staves(out)]
    return out, rot % 360, seeds, after


def main():
    ap = argparse.ArgumentParser(description="総譜 PDF のページの向きと曲がりを整える")
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--staves", type=int, default=0, help="1段組の譜表数（分かっていれば段組数の判定に使う）")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    thumbs, lines, layout = [], [], {}
    for n, im in enumerate(page_images(Path(args.pdf)), 1):
        page, rot, before, after = process_page(im)
        Image.fromarray(page.astype(np.uint8)).save(out / f"p{n:02d}.png")
        layout[f"p{n:02d}"] = {"rotation": rot, "staves": [[int(t), int(b), round(float(sp), 2)] for t, b, sp in after]}
        note = ""
        if args.staves:
            note = f" = {len(after) / args.staves:.1f} 段組" + ("" if len(after) % args.staves == 0 else "  ← 合わない")
        line = f"p{n:02d}: 回転 {rot:>3}°  中央で検出 {len(before):>2} 本 → 補正後 全幅で検出 {len(after):>2} 本{note}"
        print(line)
        lines.append(line)
        t = Image.fromarray(page.astype(np.uint8))
        t.thumbnail((420, 600))
        thumbs.append(t)
    (out / "_report.txt").write_text("\n".join(lines), encoding="utf-8")
    (out / "_layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")

    cols = 5
    tw, th = max(t.width for t in thumbs), max(t.height for t in thumbs)
    sheet = Image.new("L", (cols * tw, ((len(thumbs) + cols - 1) // cols) * th), 128)
    for k, t in enumerate(thumbs):
        sheet.paste(t, ((k % cols) * tw, (k // cols) * th))
    sheet.save(out / "_contact.png")
    print(f"→ {out}\\_contact.png で確認")


if __name__ == "__main__":
    main()
