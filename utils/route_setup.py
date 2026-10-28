"""Interactive terminal setup for a single-destination forwarding route."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telethon import utils

from .config_loader import ConfigError


@dataclass(frozen=True)
class DialogChoice:
    peer_id: int
    kind: str
    title: str
    username: str | None


def _dialog_kind(dialog: Any) -> str | None:
    if getattr(dialog, "is_group", False):
        return "GROUP"
    if getattr(dialog, "is_channel", False):
        return "CHANNEL"
    return None


async def _get_dialog_choices(client: Any) -> list[DialogChoice]:
    choices: list[DialogChoice] = []
    async for dialog in client.iter_dialogs():
        kind = _dialog_kind(dialog)
        if kind is None:
            continue
        entity = dialog.entity
        choices.append(
            DialogChoice(
                peer_id=utils.get_peer_id(entity),
                kind=kind,
                title=(dialog.name or "-").replace("\t", " ").replace("\n", " "),
                username=getattr(entity, "username", None),
            )
        )
    return choices


def _show_choices(choices: list[DialogChoice]) -> None:
    print("\nDaftar grup dan channel yang bisa diakses:")
    for index, choice in enumerate(choices, start=1):
        username = f"@{choice.username}" if choice.username else "-"
        print(f"  {index}. [{choice.kind:<7}] {choice.title}  {username}  (ID: {choice.peer_id})")


def _parse_indexes(value: str, count: int, *, multiple: bool) -> list[int] | None:
    parts = [part.strip() for part in value.split(",")]
    if not value.strip() or any(not part.isdigit() for part in parts):
        return None
    if not multiple and len(parts) != 1:
        return None
    indexes = [int(part) for part in parts]
    if any(index < 1 or index > count for index in indexes):
        return None
    return list(dict.fromkeys(indexes))


def _choose_destination(choices: list[DialogChoice]) -> int:
    while True:
        answer = input("\nPilih nomor tujuan (satu grup/channel): ")
        indexes = _parse_indexes(answer, len(choices), multiple=False)
        if indexes:
            return indexes[0] - 1
        print(f"Masukkan satu nomor dari 1 sampai {len(choices)}.")


def _choose_sources(choices: list[DialogChoice], destination_index: int) -> list[int]:
    while True:
        answer = input("Pilih nomor sumber (bisa beberapa, pisahkan dengan koma; contoh 1,3): ")
        indexes = _parse_indexes(answer, len(choices), multiple=True)
        if indexes and destination_index + 1 not in indexes:
            return [index - 1 for index in indexes]
        if indexes and destination_index + 1 in indexes:
            print("Tujuan yang dipilih tidak bisa dipakai sebagai sumber. Pilih nomor sumber lainnya.")
        else:
            print(f"Masukkan satu atau beberapa nomor dari 1 sampai {len(choices)}, dipisahkan koma.")


def _write_route(config_path: Path, sources: list[DialogChoice], destination: DialogChoice) -> None:
    if config_path.exists():
        try:
            config: Any = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"JSON tidak valid di baris {exc.lineno}, kolom {exc.colno}: {exc.msg}"
            ) from exc
        if not isinstance(config, dict):
            raise ConfigError("root harus berupa object JSON.")
    else:
        config = {
            "rules": [],
            "ignore_outgoing": True,
            "rate_limit": {
                "delay_seconds": 1.0,
                "max_attempts": 5,
                "flood_wait_buffer_seconds": 1,
            },
        }

    config["rules"] = [
        {
            "name": "rute-terminal",
            "sources": [choice.peer_id for choice in sources],
            "destinations": [destination.peer_id],
        }
    ]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def setup_route(client: Any, config_path: Path) -> None:
    choices = await _get_dialog_choices(client)
    if len(choices) < 2:
        raise ConfigError("Diperlukan minimal dua grup/channel yang bisa diakses: satu tujuan dan satu sumber.")

    _show_choices(choices)
    destination_index = _choose_destination(choices)
    source_indexes = _choose_sources(choices, destination_index)
    destination = choices[destination_index]
    sources = [choices[index] for index in source_indexes]
    _write_route(config_path, sources, destination)

    source_names = ", ".join(choice.title for choice in sources)
    print(f"\nKonfigurasi tersimpan di {config_path}.")
    print(f"Tujuan: {destination.title}")
    print(f"Sumber: {source_names}")
