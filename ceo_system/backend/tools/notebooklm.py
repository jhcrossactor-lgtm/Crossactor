"""
NotebookLM Tool — SX（デザイナー）が使用するインフォグラフィック生成ツール

現状：NotebookLM に公式APIなし（2026年時点）
準備状態：APIリリース時にここに実装を追加するだけで即稼働できる設計

実装時のチェックリスト：
  1. NOTEBOOKLM_API_KEY を Railway の環境変数に追加
  2. NotebookLMClient の実装を書く（下のスタブを埋める）
  3. /api/tools/notebooklm エンドポイントのコメントアウトを外す（main.py）
  4. SX への依頼フローで自動呼び出しを有効化

参考：
  - Google NotebookLM: https://notebooklm.google.com/
  - API情報が出たらここに追記する
"""

import os
from typing import Optional


class NotebookLMClient:
    """NotebookLM API クライアント（スタブ）"""

    def __init__(self):
        self.api_key = os.getenv("NOTEBOOKLM_API_KEY")
        self.base_url = os.getenv("NOTEBOOKLM_API_BASE_URL", "https://notebooklm.googleapis.com/v1")
        self.available = self.api_key is not None

    def is_available(self) -> bool:
        return self.available

    def create_infographic(
        self,
        content: str,
        title: Optional[str] = None,
        style: Optional[str] = None,
    ) -> dict:
        """
        NotebookLM でインフォグラフィックを生成する

        Args:
            content: ソース素材（SXが整えたテキスト・構成）
            title: インフォグラフィックのタイトル
            style: スタイル指定（例: "minimal", "colorful"）

        Returns:
            {"status": "ok", "url": "...", "file_path": "..."}

        TODO: API公開後に実装
        """
        if not self.available:
            return {
                "status": "unavailable",
                "message": (
                    "NotebookLM APIはまだ公開されていません。\n"
                    "SXが作成したソース素材をNotebookLMに手動で投入してください。\n\n"
                    f"[SXのソース素材]\n{content}"
                ),
            }

        # --- API公開後にここを実装 ---
        raise NotImplementedError("NotebookLM API実装待ち")

    def prepare_source_material(self, brief: str, data: Optional[str] = None) -> str:
        """
        SXがNotebookLM用のソース素材を整形するヘルパー

        NotebookLMに投入しやすい形にコンテンツを構造化する。
        APIの有無に関わらず常に使える。
        """
        sections = [f"# {brief}"]
        if data:
            sections.append(f"\n## データ・ファクト\n{data}")
        sections.append("\n## 出力形式\nインフォグラフィック（視覚的にわかりやすく）")
        return "\n".join(sections)


# シングルトン
notebooklm = NotebookLMClient()
