"""Resolve routes, filter messages, and forward Telegram updates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Sequence

from telethon import errors, events, utils

from .config_loader import AppConfig, MessageFilters


@dataclass(frozen=True)
class ResolvedChat:
    peer_id: int
    entity: Any
    label: str


@dataclass(frozen=True)
class ResolvedRule:
    name: str
    source_ids: frozenset[int]
    destinations: tuple[ResolvedChat, ...]
    filters: MessageFilters


def parse_entity_reference(reference: int | str) -> int | str:
    """Normalize numeric strings and @usernames accepted in config.json."""
    if isinstance(reference, int):
        return reference
    value = reference.strip()
    if value.startswith("@"):
        value = value[1:]
    if value.lstrip("-").isdigit():
        try:
            return int(value)
        except ValueError:
            pass
    return value


async def _resolve_chat(client: Any, reference: int | str) -> ResolvedChat:
    entity = await client.get_entity(parse_entity_reference(reference))
    peer_id = utils.get_peer_id(entity)
    label = getattr(entity, "title", None) or getattr(entity, "username", None) or str(peer_id)
    return ResolvedChat(peer_id=peer_id, entity=entity, label=label)


async def resolve_rules(client: Any, config: AppConfig) -> tuple[ResolvedRule, ...]:
    """Resolve configured references once so event filtering works with stable IDs."""
    resolved: list[ResolvedRule] = []
    for rule in config.rules:
        source_ids: set[int] = set()
        for source in rule.sources:
            try:
                source_ids.add((await _resolve_chat(client, source)).peer_id)
            except Exception as exc:
                raise ValueError(f"Gagal mengenali sumber {source!r} pada rule '{rule.name}': {exc}") from exc

        destinations_by_id: dict[int, ResolvedChat] = {}
        for destination in rule.destinations:
            try:
                chat = await _resolve_chat(client, destination)
            except Exception as exc:
                raise ValueError(f"Gagal mengenali tujuan {destination!r} pada rule '{rule.name}': {exc}") from exc
            destinations_by_id[chat.peer_id] = chat
        resolved.append(ResolvedRule(rule.name, frozenset(source_ids), tuple(destinations_by_id.values()), rule.filters))
    return tuple(resolved)


def _media_type(message: Any) -> str:
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None):
        return "video"
    document = getattr(message, "document", None)
    if document:
        file_info = getattr(message, "file", None)
        mime_type = getattr(file_info, "mime_type", None) or getattr(document, "mime_type", "") or ""
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        return "document"
    if getattr(message, "media", None):
        return "other"
    return "text"


def matches_filters(
    messages: Sequence[Any],
    filters: MessageFilters,
    *,
    sender_is_bot: bool | None = False,
) -> bool:
    """Return whether a message or full album satisfies a rule's filters."""
    if filters.ignore_bots and sender_is_bot is not False:
        return False

    if filters.keywords:
        content = "\n".join((getattr(message, "raw_text", None) or "") for message in messages).casefold()
        found = [keyword.casefold() in content for keyword in filters.keywords]
        if filters.keyword_mode == "all" and not all(found):
            return False
        if filters.keyword_mode == "any" and not any(found):
            return False

    if filters.media_types:
        categories = {_media_type(message) for message in messages}
        if "media" in filters.media_types and categories - {"text"}:
            return True
        if not categories.intersection(filters.media_types):
            return False

    return True


class Forwarder:
    def __init__(self, client: Any, config: AppConfig, rules: Sequence[ResolvedRule], logger: Any):
        self.client = client
        self.config = config
        self.logger = logger
        self.rules_by_source: dict[int, list[ResolvedRule]] = {}
        self.destinations: dict[int, ResolvedChat] = {}
        for rule in rules:
            for source_id in rule.source_ids:
                self.rules_by_source.setdefault(source_id, []).append(rule)
            for destination in rule.destinations:
                self.destinations[destination.peer_id] = destination
        self.source_entities = list(
            dict.fromkeys(source_id for rule in rules for source_id in rule.source_ids)
        )
        self._destination_locks: dict[int, asyncio.Lock] = {}
        self._last_send: dict[int, float] = {}

    def register_handlers(self) -> None:
        if not self.rules_by_source:
            raise ValueError("Belum ada source aktif. Tambahkan minimal satu rule di config.json.")
        chats = self.source_entities
        self.client.add_event_handler(self._handle_message, events.NewMessage(chats=chats, incoming=True))
        self.client.add_event_handler(self._handle_album, events.Album(chats=chats))

    async def _handle_message(self, event: Any) -> None:
        message = event.message
        if getattr(message, "grouped_id", None):
            return  # Album ditangani sekali melalui events.Album.
        await self._dispatch([message], event.chat_id)

    async def _handle_album(self, event: Any) -> None:
        await self._dispatch(list(event.messages), event.chat_id)

    async def _dispatch(self, messages: list[Any], source_id: int) -> None:
        if not messages:
            return
        if self.config.ignore_outgoing and any(getattr(message, "out", False) for message in messages):
            return

        candidate_rules = self.rules_by_source.get(source_id, [])
        if not candidate_rules:
            return

        sender_is_bot: bool | None = None
        if any(rule.filters.ignore_bots for rule in candidate_rules):
            sender_id = getattr(messages[0], "sender_id", None)
            if sender_id is not None:
                try:
                    sender = await self.client.get_entity(sender_id)
                    sender_is_bot = bool(getattr(sender, "bot", False))
                except Exception as exc:
                    self.logger.warning("Tidak dapat memeriksa pengirim untuk source %s: %s", source_id, exc)

        selected_destinations: dict[int, ResolvedChat] = {}
        matching_rules: list[str] = []
        for rule in candidate_rules:
            if matches_filters(messages, rule.filters, sender_is_bot=sender_is_bot):
                matching_rules.append(rule.name)
                selected_destinations.update({chat.peer_id: chat for chat in rule.destinations})

        if not selected_destinations:
            return

        for destination in selected_destinations.values():
            await self._forward_to(destination, messages, source_id, matching_rules)

    async def _forward_to(
        self,
        destination: ResolvedChat,
        messages: list[Any],
        source_id: int,
        matching_rules: list[str],
    ) -> None:
        lock = self._destination_locks.setdefault(destination.peer_id, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            attempts = self.config.rate_limit.max_attempts
            for attempt in range(1, attempts + 1):
                delay = self.config.rate_limit.delay_seconds
                elapsed = loop.time() - self._last_send.get(destination.peer_id, 0.0)
                if elapsed < delay:
                    await asyncio.sleep(delay - elapsed)
                try:
                    forwarded = await self.client.forward_messages(destination.entity, messages)
                    self._last_send[destination.peer_id] = loop.time()
                    count = len(forwarded) if isinstance(forwarded, (list, tuple)) else 1
                    self.logger.info(
                        "Forward berhasil source=%s destination=%s messages=%s rules=%s",
                        source_id,
                        destination.label,
                        count,
                        ",".join(matching_rules),
                    )
                    return
                except errors.FloodWaitError as exc:
                    self._last_send[destination.peer_id] = loop.time()
                    if attempt >= attempts:
                        self.logger.error(
                            "Flood wait berulang; forward dibatalkan source=%s destination=%s attempts=%s",
                            source_id,
                            destination.label,
                            attempts,
                        )
                        return
                    wait_seconds = int(exc.seconds) + self.config.rate_limit.flood_wait_buffer_seconds
                    self.logger.warning(
                        "Telegram meminta jeda %s detik untuk %s (percobaan %s/%s).",
                        wait_seconds,
                        destination.label,
                        attempt,
                        attempts,
                    )
                    await asyncio.sleep(wait_seconds)
                except (errors.ServerError, errors.RpcCallFailError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
                    self._last_send[destination.peer_id] = loop.time()
                    if attempt >= attempts:
                        self.logger.exception(
                            "Gangguan sementara; forward gagal source=%s destination=%s attempts=%s",
                            source_id,
                            destination.label,
                        )
                        return
                    wait_seconds = min(2 ** (attempt - 1), 30)
                    self.logger.warning(
                        "Pengiriman ke %s gagal sementara (%s); mencoba lagi dalam %s detik (%s/%s).",
                        destination.label,
                        exc,
                        wait_seconds,
                        attempt,
                        attempts,
                    )
                    await asyncio.sleep(wait_seconds)
                except Exception:
                    self.logger.exception(
                        "Forward gagal source=%s destination=%s; pesan dilewati.",
                        source_id,
                        destination.label,
                    )
                    return
