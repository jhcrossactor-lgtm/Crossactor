import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

DATA_DIR = BASE_DIR / "data"
LAW_CACHE_DIR = DATA_DIR / "law_cache"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# e-Gov 法令API
EGOV_API_BASE = "https://laws.e-gov.go.jp/api/1"
LAW_IDS = {
    "建築基準法": "322AC0000000201",
    "民法":       "129AC0000000089",
}
