"""Command-line entry point for the Telegram message forwarder."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from utils.config_loader import ConfigError, load_config
from utils.forwarder import Forwarder, resolve_rules
from utils.logging_config import configure_logging
from utils.route_setup import setup_route
from utils.settings import PROJECT_DIR, load_settings
from utils.telegram_client import create_client, start_client


async def run_forwarder(config_path: Path) -> None:
    settings = load_settings()
    logger = configure_logging(settings.log_level)
    config = load_config(config_path)
    client = create_client(settings)
    try:
        await start_client(client, settings)
        me = await client.get_me()
        logger.info("Login berhasil sebagai %s (ID %s).", me.username or me.first_name, me.id)

        if not config.rules:
            print("Belum ada routing rule. Atur tujuan dan sumber lewat pilihan nomor berikut.")
            await setup_route(client, config_path)
            config = load_config(config_path)

        rules = await resolve_rules(client, config)
        forwarder = Forwarder(client, config, rules, logger)
        forwarder.register_handlers()
        source_count = len(forwarder.rules_by_source)
        destination_count = len(forwarder.destinations)
        logger.info(
            "Forwarder aktif: %s source, %s destination, %s rule. Tekan Ctrl+C untuk berhenti.",
            source_count,
            destination_count,
            len(rules),
        )
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forward pesan Telegram berdasarkan routing rules.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "scan", "setup"),
        default="run",
        help="run memulai forwarder (default); scan menampilkan daftar grup/channel; setup memilih tujuan dan sumber.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "config.json",
        help="path file konfigurasi JSON (default: config.json di folder proyek).",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "scan":
            from scanner import scan_dialogs

            asyncio.run(scan_dialogs())
        elif args.command == "setup":
            settings = load_settings()
            client = create_client(settings)

            async def configure() -> None:
                try:
                    await start_client(client, settings)
                    await setup_route(client, args.config if args.config.is_absolute() else PROJECT_DIR / args.config)
                finally:
                    await client.disconnect()

            asyncio.run(configure())
        else:
            config_path = args.config if args.config.is_absolute() else PROJECT_DIR / args.config
            asyncio.run(run_forwarder(config_path))
    except KeyboardInterrupt:
        logging.getLogger("telegram_forwarder").info("Forwarder dihentikan.")
    except (ConfigError, ValueError) as exc:
        print(f"Konfigurasi belum siap: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
