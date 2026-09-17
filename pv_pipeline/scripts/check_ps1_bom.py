"""PowerShellスクリプトに UTF-8 BOM が付いているか確かめる。

Windows PowerShell 5.1 は BOM の無い .ps1 を ANSI(CP932)として読むため、
日本語が文字化けして構文エラーになる。編集でBOMが落ちるのを防ぐ。
"""

import sys
from pathlib import Path

BOM = b"\xef\xbb\xbf"
root = Path(__file__).resolve().parent
bad = [p.name for p in sorted(root.glob("*.ps1")) if not p.read_bytes().startswith(BOM)]
if bad:
    sys.exit("BOM が落ちている .ps1 がある（Windowsで文字化けする）: " + ", ".join(bad))
print(f"PowerShellスクリプトのBOM: OK ({len(list(root.glob('*.ps1')))}件)")
