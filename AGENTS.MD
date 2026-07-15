# CRO Agent Rules

このファイルを最初に読むこと。

- skills/: ルーティング層。各SKILL.mdのdescriptionは短いトリガー句のみ（ドキュメント化しない）
- scripts/: 依存の少ない再利用ヘルパー。繰り返しコマンドはここに集約
- hooks/: `git config core.hooksPath hooks` で有効化。コミット前にスキル検証

## 運用ルール
- ルーティンタスクはClaude Codeで初回構築→動作確認後にCLI化
- MCP接続は「常時コンテキストコストを払う価値があるか」で判断。一回学習すれば済むならCLI優先
- skill descriptionは最小トークンでルーティング用に絞る。本文との重複禁止
