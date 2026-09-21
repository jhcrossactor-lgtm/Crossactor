---
name: grilling
description: 計画・設計・要件を徹底的に問い詰めて精度を上げるヒアリングスキル。「グリルして」「詰めて」「要件を固めたい」「この計画をストレステストして」「SOW作成前」「ヒアリングして」「企画を検証して」と言われたら起動。新ツール開発・クライアント提案（松本酒造・フジヒサ等）・エージェント設計・リファクタ前に使用。
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

質問領域（必ず網羅）：
- データモデル / 入出力の定義
- エッジケース（境界値・異常系・法規制約）
- 障害モード（何が壊れうるか、壊れた時どうなるか）
- 既存システム（CRO・LINE Webhook・既存ツール群）との関連
- 成功基準（何ができたら完了か）

ルール：
- 1回に1〜3問。回答を得てから次の分岐へ
- 各質問に推奨回答を添える（ユーザーは承認 or 修正だけでよい）
- 全分岐が解決したら、確定事項のサマリーを箇条書きで出力して終了
- 曖昧な回答は流さず、具体例で確認する
