import os

from dotenv import load_dotenv

load_dotenv()

VAJRA_GATE_LOG_LEVEL = os.getenv("VAJRA_GATE_LOG_LEVEL", os.getenv("VAJRAM_LOG_LEVEL", "INFO")).upper()
VAJRA_GATE_LOG_JSON = os.getenv("VAJRA_GATE_LOG_JSON", os.getenv("VAJRAM_LOG_JSON", "")).lower() in ("1", "true")
VAJRA_GATE_PORT = int(os.getenv("VAJRA_GATE_PORT", os.getenv("VAJRAM_PORT", "8000")))
VAJRA_GATE_CHAT_LOG = os.getenv("VAJRA_GATE_CHAT_LOG", os.getenv("VAJRAM_CHAT_LOG", ""))
WORKSPACE_DIR = os.getenv("HIIL_WORKSPACE_DIR", os.getcwd())
