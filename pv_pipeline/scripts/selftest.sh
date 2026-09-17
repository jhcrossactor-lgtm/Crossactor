#!/usr/bin/env bash
# APIを一切叩かずに、配線（cuts.yaml -> stage1 -> stage2 -> 結合）を通しで確認する。
# 合成素材を projects/_selftest/ に作り、mockプロバイダで最後まで回す。
set -euo pipefail
cd "$(dirname "$0")/.."
PROJ=projects/_selftest
rm -rf "$PROJ"
mkdir -p "$PROJ/input"
cp projects/villa_test/config.yaml projects/villa_test/cuts.yaml "$PROJ/"

python3 - "$PROJ/input" <<'PY'
import sys
from pathlib import Path
from PIL import Image, ImageDraw
out = Path(sys.argv[1])
specs = [("4446557_l.jpg",(1600,1067),(70,110,160)), ("IMG_8613.jpg",(1200,1600),(60,140,100)),
         ("ICED2685.JPEG",(1440,1080),(40,130,140)), ("GGBM1602.JPEG",(1080,1440),(150,90,50)),
         ("IMG_5558.JPG",(1600,1200),(100,90,180)), ("IMG_5565.JPG",(1600,1200),(110,120,60)),
         ("IMG_8628.jpg",(1200,1600),(130,60,150)), ("IMG_5577.JPG",(1600,1200),(140,50,50)),
         ("BIEV8282.JPEG",(1440,1080),(50,80,80)), ("character_sheet.png",(1024,1024),(120,120,120))]
for name,(w,h),col in specs:
    im = Image.new("RGB",(w,h),col); d = ImageDraw.Draw(im)
    d.rectangle([20,20,w-20,h-20], outline=(255,255,255), width=8)
    d.text((60,60), f"{name}\n{w}x{h}", fill=(255,255,255))
    im.save(out/name, quality=95)
print(f"ダミー素材 {len(specs)} 件を作成")
PY

FF=$(python3 -c "import shutil,imageio_ffmpeg as i;print(shutil.which('ffmpeg') or i.get_ffmpeg_exe())")
"$FF" -y -loglevel error -f lavfi -i "testsrc=size=1080x1920:rate=30:duration=8" \
      -c:v libx264 -pix_fmt yuv420p "$PROJ/input/IMG_5625.MOV"

python3 scripts/check_ps1_bom.py

python3 run.py --project "$PROJ" check
python3 run.py --project "$PROJ" --stage 1 --provider mock --yes
python3 run.py --project "$PROJ" --stage 2 --provider mock
python3 run.py --project "$PROJ" --stage 3
python3 run.py --project "$PROJ" status

python3 - "$PROJ/output/pv_16x9.mp4" <<'PY'
import sys
sys.path.insert(0, ".")
from pathlib import Path
from pvp.util import probe_duration, has_audio_stream
out = Path(sys.argv[1])
assert out.exists(), "出力が無い"
dur = probe_duration(out)
print(f"\n結果: {out} 尺={dur:.2f}秒 音声={'あり' if has_audio_stream(out) else 'なし'}")
assert 31.0 < dur < 32.0, f"尺が想定外: {dur}"
print("セルフテスト合格")
PY
