"""Central configuration. Everything is overridable from .env"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- LLM ------------------------------------------------------------------
# Both xAI (Grok) and Groq expose OpenAI-compatible endpoints, so one client
# works for either. Pick with LLM_PROVIDER.
PROVIDERS = {
    "xai":  {"base_url": "https://api.x.ai/v1",            "key_env": "XAI_API_KEY"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "xai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "grok-4-1-fast-non-reasoning")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# --- Data hub -------------------------------------------------------------
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
UPLOAD_DIR = DATA_DIR / "uploads"
DOCS_DIR = BASE_DIR / os.getenv("DOCS_DIR", "docs")
STORAGE_DIR = BASE_DIR / "storage"
SQL_MAX_RETRIES = int(os.getenv("SQL_MAX_RETRIES", "3"))
SQL_ROW_LIMIT = int(os.getenv("SQL_ROW_LIMIT", "200"))

# --- RAG ------------------------------------------------------------------
CHROMA_DIR = STORAGE_DIR / "chroma"
CHROMA_COLLECTION = "company_docs"
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")   # local, free
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

for d in (DATA_DIR, UPLOAD_DIR, DOCS_DIR, STORAGE_DIR):
    d.mkdir(parents=True, exist_ok=True)
