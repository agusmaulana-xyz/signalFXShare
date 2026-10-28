"""Telegram client construction and first-login prompts."""

from __future__ import annotations

from getpass import getpass

from telethon import TelegramClient

from .settings import Settings


def create_client(settings: Settings) -> TelegramClient:
    # Set flood_sleep_threshold=0 so the forwarder can log and control each wait.
    return TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
        flood_sleep_threshold=0,
        request_retries=3,
        connection_retries=5,
        retry_delay=2,
        raise_last_call_error=True,
    )


def phone_prompt() -> str:
    return input("Nomor telepon Telegram (format internasional): ").strip()


def password_prompt() -> str:
    return getpass("Password verifikasi dua langkah Telegram: ")


async def start_client(client: TelegramClient, settings: Settings) -> None:
    await client.start(phone=settings.phone or phone_prompt, password=password_prompt)
