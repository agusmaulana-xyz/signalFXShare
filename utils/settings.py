"""Environment and path configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str | None
    session_path: Path
    log_level: str


def load_settings() -> Settings:
    """Load .env from the project folder and require Telegram API credentials."""
    load_dotenv(PROJECT_DIR / ".env")

    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    if not api_id_raw or not api_hash:
        raise ValueError("API_ID dan API_HASH belum diisi. Salin .env.example menjadi .env lalu isi kredensial Telegram.")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ValueError("API_ID harus berupa angka.") from exc
    if api_id <= 0:
        raise ValueError("API_ID harus berupa angka positif.")

    session_value = os.getenv("SESSION_PATH", "sessions/telegram_forwarder").strip()
    if not session_value:
        raise ValueError("SESSION_PATH tidak boleh kosong.")
    session_path = Path(session_value).expanduser()
    if not session_path.is_absolute():
        session_path = PROJECT_DIR / session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    return Settings(api_id, api_hash, os.getenv("PHONE", "").strip() or None, session_path, log_level)
