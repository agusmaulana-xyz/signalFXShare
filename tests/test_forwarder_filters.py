import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telethon import errors

from utils.config_loader import AppConfig, MessageFilters, RateLimit
from utils.forwarder import Forwarder, ResolvedChat, ResolvedRule, matches_filters, parse_entity_reference


def message(text="", *, media=None, photo=None, video=None, document=None, mime_type=None):
    file_info = SimpleNamespace(mime_type=mime_type) if mime_type else None
    return SimpleNamespace(
        raw_text=text,
        media=media,
        photo=photo,
        video=video,
        document=document,
        file=file_info,
    )


class ForwarderFilterTests(unittest.TestCase):
    def test_matches_keyword_case_insensitively(self):
        filters = MessageFilters(keywords=("signal",))
        self.assertTrue(matches_filters([message("New SIGNAL")], filters))
        self.assertFalse(matches_filters([message("market update")], filters))

    def test_keyword_all_requires_each_term(self):
        filters = MessageFilters(keywords=("gold", "silver"), keyword_mode="all")
        self.assertFalse(matches_filters([message("gold update")], filters))
        self.assertTrue(matches_filters([message("gold and silver")], filters))

    def test_media_filter_matches_album_if_any_item_matches(self):
        filters = MessageFilters(media_types=("photo",))
        album = [message(media=object()), message(media=object(), photo=object())]
        self.assertTrue(matches_filters(album, filters))
        self.assertFalse(matches_filters([message("just text")], filters))

    def test_video_documents_are_classified_from_mime_type(self):
        filters = MessageFilters(media_types=("video",))
        self.assertTrue(matches_filters([message(media=object(), document=object(), mime_type="video/mp4")], filters))

    def test_media_filter_and_keyword_filter_both_apply(self):
        filters = MessageFilters(keywords=("daily",), media_types=("photo",))
        self.assertTrue(matches_filters([message("daily", photo=object())], filters))
        self.assertFalse(matches_filters([message("daily")], filters))
        self.assertFalse(matches_filters([message("weekly", photo=object())], filters))

    def test_media_selector_matches_any_non_text_item(self):
        self.assertTrue(matches_filters([message(media=object())], MessageFilters(media_types=("media",))))
        self.assertFalse(matches_filters([message("text")], MessageFilters(media_types=("media",))))

    def test_can_ignore_bot_senders(self):
        filters = MessageFilters(ignore_bots=True)
        self.assertFalse(matches_filters([message("news")], filters, sender_is_bot=True))
        self.assertTrue(matches_filters([message("news")], filters, sender_is_bot=False))
        self.assertFalse(matches_filters([message("news")], filters, sender_is_bot=None))

    def test_normalizes_numeric_ids_and_usernames(self):
        self.assertEqual(parse_entity_reference("-100123"), -100123)
        self.assertEqual(parse_entity_reference("@my_channel"), "my_channel")


class ForwarderDispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.destination = ResolvedChat(900, "destination", "destination")
        self.message_one = message("first", media=object(), photo=object())
        self.message_two = message("second", media=object(), photo=object())
        self.client = Mock()
        self.client.forward_messages = AsyncMock(return_value=[object(), object()])
        self.logger = Mock()

    def forwarder(self, rules, *, attempts=1, buffer=0):
        config = AppConfig((), True, RateLimit(0, attempts, buffer))
        return Forwarder(self.client, config, rules, self.logger)

    async def test_album_is_forwarded_as_a_single_message_group(self):
        rule = ResolvedRule("album", frozenset({-1001}), (self.destination,), MessageFilters())
        forwarder = self.forwarder([rule])

        await forwarder._dispatch([self.message_one, self.message_two], -1001)

        self.client.forward_messages.assert_awaited_once_with(
            "destination", [self.message_one, self.message_two]
        )

    async def test_overlapping_rules_do_not_duplicate_same_destination(self):
        first = ResolvedRule("first", frozenset({-1001}), (self.destination,), MessageFilters())
        second = ResolvedRule("second", frozenset({-1001}), (self.destination,), MessageFilters())
        forwarder = self.forwarder([first, second])

        await forwarder._dispatch([self.message_one], -1001)

        self.client.forward_messages.assert_awaited_once()

    async def test_outgoing_messages_are_skipped(self):
        rule = ResolvedRule("route", frozenset({-1001}), (self.destination,), MessageFilters())
        forwarder = self.forwarder([rule])
        outgoing = message("own message")
        outgoing.out = True

        await forwarder._dispatch([outgoing], -1001)

        self.client.forward_messages.assert_not_awaited()

    async def test_bot_filter_fails_closed_when_sender_cannot_be_resolved(self):
        rule = ResolvedRule(
            "route", frozenset({-1001}), (self.destination,), MessageFilters(ignore_bots=True)
        )
        forwarder = self.forwarder([rule])

        await forwarder._dispatch([message("unknown sender")], -1001)

        self.client.forward_messages.assert_not_awaited()

    async def test_flood_wait_is_obeyed_before_retry(self):
        self.client.forward_messages = AsyncMock(
            side_effect=[errors.FloodWaitError(None, capture=3), [object(), object()]]
        )
        rule = ResolvedRule("route", frozenset({-1001}), (self.destination,), MessageFilters())
        forwarder = self.forwarder([rule], attempts=2, buffer=1)

        with patch("utils.forwarder.asyncio.sleep", new_callable=AsyncMock) as sleep:
            await forwarder._dispatch([self.message_one, self.message_two], -1001)

        self.assertEqual(self.client.forward_messages.await_count, 2)
        sleep.assert_awaited_once_with(4)


if __name__ == "__main__":
    unittest.main()
