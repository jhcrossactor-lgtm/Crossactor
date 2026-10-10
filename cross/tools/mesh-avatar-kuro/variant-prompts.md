# 差分絵（目閉じ・母音の口）を ChatGPT で作る

Mesh Avatar Studio の `variant-requests.py` が作る英語プロンプトを、キャラクターシート
（未来派ホログラム執事／青いホログラムスーツの紳士）の絵柄に合わせた日本語版にしたもの。

## 1. マスクとフォルダを作る（リポジトリ直下）

```sh
uv run tools/variant-requests.py projects/kuro
```

`projects/kuro/variant-requests/<variant>/mask.png` が 7 つできる。透明＝描き直してよい場所、不透明＝守る場所。

## 2. ChatGPT に渡すもの

毎回、**source.png ＋ その差分の mask.png ＋ キャラクターシート** の 3 枚を添付して、下の共通指示 → 個別指示の順で送る。1 回のチャットで 1 差分。

### 共通指示（毎回先頭に付ける）

```
添付の source.png は 2D アバター用の立ち絵です。これを「画像編集」で部分修正してください。
・出力は source.png と完全に同じピクセルサイズの RGBA PNG（透過背景のまま）。切り抜き・リサイズ・位置ずらし禁止。
・mask.png の透明な部分だけを描き直し、不透明な部分は 1 ピクセルも変えない。
・絵柄・線の太さ・肌色・髪・服・ポーズ・背景はそのまま。キャラクターシートの画風（青いホログラムの光沢、硬質で清潔な線）に合わせる。
・変更はマスクの縁から 4 ピクセル以上内側に収める。
```

### 個別指示（7 つ）

| 差分 | ファイル名 | 指示 |
|---|---|---|
| 目閉じ | `eyes_closed` | 両目を自然に閉じる。片目につき上まつ毛の線 1 本だけの、きれいな閉じ目。虹彩と白目は完全に消す。眉は変えない。 |
| 半目 | `eyes_half` | 両目を半分閉じる。上まぶたを目の高さの半分まで下ろし、虹彩は上まぶたの下にだけ見える。視線の向きは元のまま。 |
| 笑い目 | `eyes_smile` | 両目を「にっこり」の上向きの弧で閉じる。まつ毛はきれいに、虹彩も白目も見せない。眉は変えない。 |
| あ | `mouth_a` | 口を日本語の「あ」で縦に自然に開ける。上の歯を少しと、舌をわずかに見せる。顎の輪郭は変えない。 |
| あ（半開き） | `mouth_a_half` | 「あ」の半分の開き。小さく、やわらかく開いた口。 |
| い | `mouth_i` | 日本語の「い」。横に広く、縦に狭く開いた口。上の歯を少し見せる。 |
| お | `mouth_o` | 日本語の「お」。小さく丸く開いた口。 |

ChatGPT が「同じ人物として描き直す」方向に寄ってしまったら、「これは**部分編集**です。マスクの外は触らないで、元の画像をそのまま返してください」と言い直す。

## 3. 取り込み（ChatGPT は外側も微妙に変える前提）

ChatGPT の出力はほぼ必ず全体が再圧縮・微小にずれるので、そのままでは `build-sprites.py` に拒否される。
同梱の合成スクリプトで「外側は source.png のまま、内側だけ生成画像」に作り直す。

```sh
uv run tools/merge-variant.py projects/kuro eyes_closed  ~/Downloads/eyes_closed.png
uv run tools/merge-variant.py projects/kuro mouth_a      ~/Downloads/mouth_a.png
# …7 つぶん。位置がずれて二重に見えるなら --shift dx dy で合わせる
uv run tools/build-sprites.py projects/kuro
npm run render-poses -- projects/kuro
```

`review/` の目閉じ・口のコマを見て、残った虹彩の点やまつ毛の二重線があればその差分だけ作り直す。
