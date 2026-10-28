"""Load and validate routing configuration from JSON."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_MEDIA_TYPES = {"text", "photo", "video", "document", "audio", "other", "media"}


class ConfigError(ValueError):
    """Raised when config.json is missing or invalid."""


@dataclass(frozen=True)
class MessageFilters:
    keywords: tuple[str, ...] = ()
    keyword_mode: str = "any"
    media_types: tuple[str, ...] = ()
    ignore_bots: bool = False


@dataclass(frozen=True)
class RateLimit:
    delay_seconds: float = 1.0
    max_attempts: int = 5
    flood_wait_buffer_seconds: int = 1


@dataclass(frozen=True)
class RuleConfig:
    name: str
    sources: tuple[int | str, ...]
    destinations: tuple[int | str, ...]
    filters: MessageFilters


@dataclass(frozen=True)
class AppConfig:
    rules: tuple[RuleConfig, ...]
    ignore_outgoing: bool
    rate_limit: RateLimit


def _expect_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{path} harus berupa object JSON.")
    return value


def _expect_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{path} harus bernilai true atau false.")
    return value


def _entity_list(value: Any, path: str) -> tuple[int | str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{path} harus berupa array yang berisi minimal satu ID atau username.")

    entities: list[int | str] = []
    for index, entity in enumerate(value):
        item_path = f"{path}[{index}]"
        if isinstance(entity, bool) or not isinstance(entity, (int, str)):
            raise ConfigError(f"{item_path} harus berupa ID angka atau username string.")
        if isinstance(entity, str):
            entity = entity.strip()
            if not entity:
                raise ConfigError(f"{item_path} tidak boleh kosong.")
            if entity.startswith("@"):
                entity = entity[1:]
            if not entity:
                raise ConfigError(f"{item_path} harus memuat username setelah tanda @.")
        entities.append(entity)
    return tuple(entities)


def _filters(value: Any, path: str) -> MessageFilters:
    if value is None:
        value = {}
    data = _expect_object(value, path)

    keywords_value = data.get("keywords", [])
    if not isinstance(keywords_value, list) or any(not isinstance(item, str) for item in keywords_value):
        raise ConfigError(f"{path}.keywords harus berupa array string.")
    keywords = tuple(item.strip() for item in keywords_value if item.strip())

    keyword_mode = data.get("keyword_mode", "any")
    if not isinstance(keyword_mode, str) or keyword_mode not in {"any", "all"}:
        raise ConfigError(f"{path}.keyword_mode hanya boleh bernilai 'any' atau 'all'.")

    media_value = data.get("media_types", [])
    if not isinstance(media_value, list) or any(not isinstance(item, str) for item in media_value):
        raise ConfigError(f"{path}.media_types harus berupa array string.")
    media_types = tuple(item.strip().casefold() for item in media_value if item.strip())
    invalid_types = sorted(set(media_types) - SUPPORTED_MEDIA_TYPES)
    if invalid_types:
        options = ", ".join(sorted(SUPPORTED_MEDIA_TYPES))
        raise ConfigError(f"{path}.media_types memuat nilai tidak dikenal {invalid_types}; pilihan: {options}.")

    ignore_bots = _expect_bool(data.get("ignore_bots", False), f"{path}.ignore_bots")
    return MessageFilters(keywords, keyword_mode, media_types, ignore_bots)


def _rate_limit(value: Any) -> RateLimit:
    data = _expect_object(value, "rate_limit")
    delay = data.get("delay_seconds", 1.0)
    if (
        isinstance(delay, bool)
        or not isinstance(delay, (int, float))
        or delay > 86_400
        or not math.isfinite(delay)
        or delay < 0
    ):
        raise ConfigError("rate_limit.delay_seconds harus berupa angka antara 0 dan 86400.")

    attempts = data.get("max_attempts", 5)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 20:
        raise ConfigError("rate_limit.max_attempts harus berupa integer antara 1 dan 20.")

    buffer = data.get("flood_wait_buffer_seconds", 1)
    if isinstance(buffer, bool) or not isinstance(buffer, int) or buffer < 0:
        raise ConfigError("rate_limit.flood_wait_buffer_seconds harus berupa integer >= 0.")
    return RateLimit(float(delay), attempts, buffer)


def load_config(path: Path) -> AppConfig:
    """Read *path*, validate supported options, and return immutable settings."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"File konfigurasi tidak ditemukan: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON tidak valid di baris {exc.lineno}, kolom {exc.colno}: {exc.msg}") from exc

    root = _expect_object(raw, "root")
    rules_value = root.get("rules", [])
    if not isinstance(rules_value, list):
        raise ConfigError("rules harus berupa array.")

    rules: list[RuleConfig] = []
    for index, value in enumerate(rules_value):
        path_prefix = f"rules[{index}]"
        data = _expect_object(value, path_prefix)
        name = data.get("name", f"rule-{index + 1}")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{path_prefix}.name harus berupa string yang tidak kosong.")
        rules.append(
            RuleConfig(
                name=name.strip(),
                sources=_entity_list(data.get("sources"), f"{path_prefix}.sources"),
                destinations=_entity_list(data.get("destinations"), f"{path_prefix}.destinations"),
                filters=_filters(data.get("filters", {}), f"{path_prefix}.filters"),
            )
        )

    ignore_outgoing = _expect_bool(root.get("ignore_outgoing", True), "ignore_outgoing")
    rate_limit = _rate_limit(root.get("rate_limit", {}))
    return AppConfig(tuple(rules), ignore_outgoing, rate_limit)
