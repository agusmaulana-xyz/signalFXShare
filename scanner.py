"""List the groups and channels visible to the configured Telegram account."""

from __future__ import annotations

import asyncio

from telethon import utils

from utils.logging_config import configure_logging
from utils.settings import load_settings
from utils.telegram_client import create_client, start_client


def _dialog_kind(dialog: object) -> str | None:
    if getattr(dialog, "is_group", False):
        return "GROUP"
    if getattr(dialog, "is_channel", False):
        return "CHANNEL"
    return None


async def scan_dialogs() -> None:
    settings = load_settings()
    logger = configure_logging(settings.log_level)
    client = create_client(settings)
    try:
        await start_client(client, settings)
        print("TYPE\tID\tUSERNAME\tTITLE")
        async for dialog in client.iter_dialogs():
            kind = _dialog_kind(dialog)
            if kind is None:
                continue
            entity = dialog.entity
            peer_id = utils.get_peer_id(entity)
            username = getattr(entity, "username", None) or "-"
            title = (dialog.name or "-").replace("\t", " ").replace("\n", " ")
            print(f"{kind}\t{peer_id}\t{username}\t{title}")
        logger.info("Pemindaian dialog selesai.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(scan_dialogs())
    except KeyboardInterrupt:
        pass
    except ValueError as exc:
        print(f"Konfigurasi belum siap: {exc}")
        raise SystemExit(2) from exc
