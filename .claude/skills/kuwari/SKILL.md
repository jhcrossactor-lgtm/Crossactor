---
name: kuwari
description: 戸建分譲の区画割り自動生成システム「kuwari」の開発作業を開始・継続する。トリガーは「/kuwari」「区画割り」「くわり」「帯分解」「専通」「旗竿地の割付」「分譲の区画を切る」。敷地DXF/PDFから3階建て分譲住宅の区画割り案を生成しDXF+PDFで出力するPython CLIツールの実装・修正・テストに使う。ただし木造ハイツの配置検討（haichi-tool）や、区画割りと無関係な建築法規調査（arch-reg-sync）では起動しない。
---

# kuwari — 戸建分譲 区画割り自動生成システム 作業モード

`/kuwari` と言われたら、このプロジェクトの作業を始める。別ディレクトリで起動していても下記のパスを使う。

## 場所

| 対象 | パス |
|---|---|
| 作業フォルダ | `G:\ClaudeLocal\kuwari\` |
| venv | `G:\ClaudeLocal\venvs\kuwari`（2026-09-22 に旧 `G:\venvs` から移設。Drive同期外） |
| Python | 3.13.3 |
| 仕様書（唯一のソース） | `G:\ClaudeLocal\kuwari\SPEC.md` |
| 進捗 | `G:\ClaudeLocal\kuwari\README.md` の「進捗」 |
| GitHub | `Fujihisahousing/kuwari`（**private**。rentbook とは別リポジトリ） |

git は `safe.directory` 登録済み。デフォルトブランチは `main`。
`G:\ClaudeLocal` は OneDrive・Google Drive のどちらの同期対象でもない（Drive が `.git` を同期して壊すのを避けるため）。
**private だが doctrine.yaml は設計ノウハウそのもの。public 化しない。**

## 起動時にやること

1. `SPEC.md` を読む。**仕様の判断はここだけを根拠にする。会話の記憶で補わない。**
2. `README.md` の「進捗」チェックリストで、どの Step まで終わっているかを確認する。
3. テストを流して現状を把握する。

```bash
"G:/ClaudeLocal/venvs/kuwari/Scripts/python.exe" -m pytest
```

## よく使うコマンド

テスト（全件）:

```bash
cd "G:/ClaudeLocal/kuwari" && "G:/ClaudeLocal/venvs/kuwari/Scripts/python.exe" -m pytest
```

DXF の中身を目視確認:

```bash
cd "G:/ClaudeLocal/kuwari" && "G:/ClaudeLocal/venvs/kuwari/Scripts/python.exe" scripts/inspect_dxf.py tests/fixtures/test2.dxf
```

依存の再インストール:

```bash
"G:/ClaudeLocal/venvs/kuwari/Scripts/python.exe" -m pip install -r "G:/ClaudeLocal/kuwari/requirements.txt"
```

区画割りを実行（DXF + PDF を out/ に出す。--answer で正解図を重ねて境界一致率を出す）:

```bash
cd "G:/ClaudeLocal/kuwari" && "G:/ClaudeLocal/venvs/kuwari/Scripts/python.exe" cli.py tests/fixtures/test2.dxf --out out --answer tests/fixtures/test2-A.dxf
```

Streamlit UI（Step 9 以降）:

```bash
cd "G:/ClaudeLocal/kuwari" && "G:/ClaudeLocal/venvs/kuwari/Scripts/streamlit.exe" run ui/fix_coords.py
```

PowerShell 5.1 なので `&&` は使えない。ユーザーに渡すコマンドは1ブロック1コマンドにするか `;` でつなぐ。

## 作業のルール（SPEC.md の要点。詳細は必ず SPEC.md を見る）

- **法規の数値を推測で埋めない。** 未確認は `TODO(未確定)` ＋ `verified_at: null`。黙って仮値を入れるのが最悪の失敗。
- **法規はコードでなくデータ。** `if 大阪市:` を書き始めたら設計が壊れている。`regulation/rules/*.yaml` に足す。
- **LLM は抽出のみ。** 判定・区画割り・幾何演算に LLM の出力を流さない。決定論的な層と物理的に分ける。
- **`Lot.polygon`（竿込み）と `Lot.effective_polygon`（竿を除く）を必ず別フィールドで持つ。** 一本化すると旗竿地で破綻する。
- **帯分解が中核。** 専通は余りに差し込むものではなく、最初から〈前面区画 + 専通〉の割付単位。この発想を外すと test2 が 15区画にしかならない。
- **mm 単位の整数に正規化してから幾何演算する。** 測量座標は X=北 / Y=東。
- **SB判定は必ず `min_distance(building_polygon, boundary_line)` を通す。** 直交ケースを特別扱いしない。
- DXF は `ezdxf.readfile(path, encoding='cp932')`。出力レイヤは `敷地 / 区画界 / 建物 / 専通 / 道路 / 寸法 / 文字` で固定。
- **各 Step が終わったら報告し、次に進む前にユーザー確認を取る。**
- 依頼された範囲外のコードは触らない。Step ごとにコミットを分ける。

## 回帰テストの正解値（ルールを1つ足すたびに3件回す）

| fixture | 敷地 | 道路 | 正解 |
|---|---|---|---|
| test.dxf | 22,400 × 26,000 = 582.40㎡ | 北7,000 / 東5,000 / 南5,000 (42-1-1) | **8区画**（旗竿なし） |
| test2.dxf | 33,200 × 38,000 = 1,261.60㎡ | 北7,000 / 南4,000 | **16区画**（前面8 + 旗竿8） |
| test3.dxf | 32,700 × 37,400 = 1,222.98㎡ | 北7,000 / 東6,500 / 南4,600 | **16区画**（直接接道10 + 旗竿6） |

既知の入力データの不備（SPEC.md に記載済み。修正せず、検出できることをテストする）:

- `test.dxf` の面積テキストは **291.200㎡** だが幾何は **582.400㎡**（ちょうど2倍）。幾何が正。
- `test3.dxf` の北辺寸法テキストは **33,200** だが実測は **32,700**。実測が正。面積テキストは無い。
- `test2-A.dxf` の南側外端2区画（5,400 / 2,900）は作図ミス。正しくは **5,700 / 2,600**。

## 仕様を変えるとき

SPEC.md を書き換える前に必ずユーザー確認を取り、変更点を SPEC.md 末尾の「改訂履歴」に残す。
