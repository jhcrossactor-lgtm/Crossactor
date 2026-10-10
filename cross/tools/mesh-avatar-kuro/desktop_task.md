# デスクトップの Claude に貼る作業指示（クロのアバター化）

前提：`G:\ClaudeLocal\cross` が最新（`scripts\update.ps1` 実行済み）。
立ち絵 PNG とキャラクターシートはデスクトップにある。下の `<...>` を実ファイル名に置き換えて貼る。

---

```
# 目的
ChatGPT で作った AI キャラ「クロ」の立ち絵を、Mesh Avatar Studio で VTuber のように滑らかに動く
2D アバターにし、足元から立ち上るデジタル粒子エフェクトを付ける。

# 入力
- 立ち絵：C:\Users\<ユーザー名>\Desktop\<立ち絵>.png
- キャラクターシート：C:\Users\<ユーザー名>\Desktop\未来派ホログラム執事 キャラクターシート.png
  （絵柄・配色・表情の参照用。青いホログラムスーツの紳士）
- 追加キット：G:\ClaudeLocal\cross\tools\mesh-avatar-kuro\（README.md を最初に読む）

# 手順
1. 準備
   - G:\ClaudeLocal\ に https://github.com/shinshin86/mesh-avatar-studio を git clone し、npm install。
   - Node.js 22.17+、Python 3.10+、uv を確認。無ければ何が無いかを報告して停止。
   - npx playwright install chromium（render-poses に必要）。
   - 自分のアカウントで G:\ClaudeLocal\mesh-avatar-studio\projects\ フォルダを作っておく（README.ja.md の Windows 注意）。
2. README.ja.md、docs/agent-guide.md、docs/rig-fields.md、docs/reference.md を全部読む。
   agent-guide の「Vision check」を実行し、スコアを報告する。不合格なら停止して報告。
   自分が Claude Opus 5.5 以外で動いているなら、その旨も報告する（手順書の推奨モデル）。
3. 立ち絵の事前チェック（作業前に結果を一度報告）
   - 正面〜やや斜め、胸から上、背景透過か。透過でなければ rembg で抜く（uv run --with rembg … か、画像をこちらに戻して指示を待つ）。
   - 立ち絵に描き込まれたエフェクト（光の粒・線・オーラ）があれば、アバター化の邪魔なので消した版を使う。
   - 横向き・全身・手で顔が隠れている、など条件を大きく外れる場合は報告して止まる。
4. docs/agent-guide.md の手順どおりにアバター化し、projects/kuro/ に保存する。
   拡大グリッドで座標を読む、overlay で確認する、render-poses で全ポーズを見る、を省略しない。
5. 「VTuber 的な滑らかさ」に調整する。
   G:\ClaudeLocal\cross\tools\mesh-avatar-kuro\rig-tuning.md を読み、
   - rig.json 側は表 A に寄せる（まず起点値で作って破綻を直してから）
   - 待機中の呼吸・揺れ・髪の遅れ・首振りの量は、本体を改変せず stream-fx.html の calm / sway / talk で落とす（表 B）
   - 変更した rig.json の値は「フィールド・変更前・変更後・理由」で全部記録する
6. エディタ（npm run dev）の「ポーズ確認」「口の動き」で全ポーズと あ・い・う・え・お・ん を確認し、
   メッシュの破れ・目や口のはみ出し・髪の不自然な伸びがあれば直す（最大 3 周。残りは報告）。
7. 目閉じ・母音口の差分絵
   - uv run tools/variant-requests.py projects/kuro でマスクを作る。
   - 画像生成はこちら（ほせもやん）が ChatGPT で行う。G:\ClaudeLocal\cross\tools\mesh-avatar-kuro\variant-prompts.md の
     プロンプトを、キャラクターシートの絵柄に合わせて必要なら微調整し、「どのファイルを添付して何を送るか」を一覧で出して止まる。
   - 生成画像を渡されたら tools/merge-variant.py → tools/build-sprites.py → render-poses で取り込み、結果を確認する。
8. デジタル粒子エフェクト
   - node G:\ClaudeLocal\cross\tools\mesh-avatar-kuro\install.mjs G:\ClaudeLocal\mesh-avatar-studio を実行（本体ファイルは上書きしない）。
   - http://127.0.0.1:5173/stream-fx.html?project=kuro を開き、粒子が足元から立ち上って上で消えること、
     口パク中（エディタの「口の動き」で文章再生、または Live ページのマイク）に粒子量と明るさが上がることを確認。
   - 色・量・速度・明るさは src/fx/digital-rise.config.js で調整。キャラクターシートの配色に合わせる。
   - コンソールの kuroFx.getStats() で fps を確認。60 を切るなら density が自動で下がっているはず。下がりすぎるなら count を減らす。
   - エフェクトは本体の rig 処理と無関係の独立レイヤーなので、本体側のコードは触らない。

# 禁止
- 立ち絵・シート・生成物を projects/ の外へコピー、アップロード、コミットしない（ChatGPT への添付はこちらがやる）。
- samples/ と reference/ を変えない。
- 座標を拡大グリッド無しで目分量で置かない。確認画像を見ずに完了と言わない。

# 完了時の報告（短く）
- 起動方法とプロジェクト名（npm run dev → エディタで projects/kuro、配信は stream-fx.html?project=kuro）
- 調整した値の一覧（rig.json：変更前→後。stream-fx：calm / sway / talk / motions）
- エフェクトの設定ファイルの場所と主な調整項目
- 残っている不自然な箇所（どのポーズ・どの部位）
- ChatGPT に渡す差分絵の添付ファイルとプロンプト、生成後の取り込みコマンド
```
