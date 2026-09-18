# IeGen：木造3階建て建売プラン自動作成

## 原則
- 生成=LLM、判定=engine/checker.py。LLMに法規合否を出させない
- 全判定に根拠（法令ID・条項・qa_ref・取得日）。根拠なし＝「要確認」
- 解釈優先：近畿共通取扱い集 > 特定行政庁取扱い > 府質疑応答集7版 > 防火避難解説。条文原文はe-Gov
- 質疑応答集6版は参考のみ（stale）
- 寸法はmm、モジュール900（config.yaml）
- Web事例は特徴量のみ保存、画像は外部公開しない
- 高リスク判断（容積・法規）は着手前に確認を取る

## 構成
docs/SOW.md 仕様 / docs/CONTEXT.md 経緯・ゲート・フェーズ / config.yaml 既定値 / law/ 法令 / rules/ 判定ルール / patterns/ 事例 / engine/ 実装 / designer_profile/ 設計思想 / tests/golden/ 正解

## 作業
- 現在フェーズ：tasks/ の最新ファイル
- 完了したらチェックを付け、差分を1行でtasks/log.mdへ

## 自走ルール
- フェーズ開始時：docs/SOW.md の該当フェーズと前フェーズの tasks/log.md を読み、tasks/phaseN.md（チェックリスト・完了基準・想定ゲート）を自分で作成してから着手
- タスク完了ごとに phaseN.md にチェック、tasks/log.md に1行記録、git commit
- フェーズ完了時：完了基準を自己検証 → tasks/phaseN_report.md（成果・未解決・次フェーズへの申し送り）を作成 → 次フェーズへ自動移行
- 失敗は同一手段で3回まで。超えたら代替案を試し、それでも駄目ならゲートとして設計者に聞く
- コンテキストが長くなったら tasks/ に状態を書き出してから要約・継続（再開時は tasks/ を読めば続行できる状態を常に保つ）
- LLMに法規合否を判定させない。判定は engine/checker.py のみ
- 根拠（法令ID・条項・qa_ref・取得日）のないルールは verified: true にしない
- Web事例画像は外部送信・公開しない
- 確認ゲート G0〜G6（docs/CONTEXT.md）以外では止まらない
