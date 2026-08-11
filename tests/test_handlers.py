"""Tests for bot handlers."""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TimedOut

from paperless_bot.api.client import Document, TaskResult
from paperless_bot.bot.handlers import (
    TELEGRAM_FILE_LIMIT,
    PaperlessBot,
    _error_handler,
    _post_init,
    _safe_edit,
    create_bot,
)
from paperless_bot.config import Config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    cfg = MagicMock(spec=Config)
    cfg.paperless_url = "http://localhost:8000"
    cfg.paperless_token = "test-token"
    cfg.paperless_public_url = "http://localhost:8000"
    cfg.telegram_bot_token = "bot-token-123"
    cfg.telegram_allowed_users = set()
    cfg.max_search_results = 10
    cfg.remove_inbox_on_done = True
    cfg.inbox_tag = None
    cfg.upload_task_timeout = 300
    cfg.health_port = 8080
    cfg.log_level = 20
    return cfg


@pytest.fixture
def bot(config):
    return PaperlessBot(config)


def _make_update(user_id=12345, chat_id=100, text=None, *, authorized=True):
    """Create a mock Update with sensible defaults."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    update.message.text = text or ""
    update.message.date = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
    return update


def _make_callback_update(user_id=12345, chat_id=100, data=""):
    """Create a mock Update with callback_query."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.callback_query.answer = AsyncMock()
    update.callback_query.from_user.id = user_id
    update.callback_query.data = data
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    return update


def _make_doc(
    doc_id=42,
    title="Test Doc",
    correspondent="ACME",
    document_type="Bill",
    tags=None,
    created="2025-01-15",
    added="2025-01-15",
    content=None,
):
    return Document(
        id=doc_id,
        title=title,
        correspondent=correspondent,
        document_type=document_type,
        tags=tags or ["invoice"],
        created=created,
        added=added,
        content=content,
    )


# ---------------------------------------------------------------------------
# _safe_edit
# ---------------------------------------------------------------------------


class TestSafeEdit:
    async def test_success(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock()
        result = await _safe_edit(msg, "hello")
        assert result is True
        msg.edit_text.assert_awaited_once_with("hello")

    async def test_bad_request(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=BadRequest("Message not modified"))
        result = await _safe_edit(msg, "hello")
        assert result is False

    async def test_timed_out(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=TimedOut())
        result = await _safe_edit(msg, "hello")
        assert result is False

    async def test_network_error(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=NetworkError("Connection reset"))
        result = await _safe_edit(msg, "hello")
        assert result is False

    async def test_passes_kwargs(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock()
        await _safe_edit(msg, "hello", parse_mode=ParseMode.MARKDOWN)
        msg.edit_text.assert_awaited_once_with("hello", parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# PaperlessBot authorization
# ---------------------------------------------------------------------------


class TestAuthorization:
    def test_authorized_empty_allowlist(self, bot):
        bot.config.telegram_allowed_users = set()
        assert bot._is_authorized(12345) is True

    def test_authorized_in_list(self, bot):
        bot.config.telegram_allowed_users = {12345, 67890}
        assert bot._is_authorized(12345) is True

    def test_unauthorized(self, bot):
        bot.config.telegram_allowed_users = {12345}
        assert bot._is_authorized(99999) is False

    async def test_check_auth_authorized(self, bot):
        update = _make_update(user_id=12345)
        bot.config.telegram_allowed_users = set()
        result = await bot._check_auth(update)
        assert result is True

    async def test_check_auth_denied(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        result = await bot._check_auth(update)
        assert result is False
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_document_url(self, bot):
        url = bot._document_url(42)
        assert url == "http://localhost:8000/documents/42/details"

    def test_user_visible_tags_excludes_inbox(self, bot):
        bot.client._tags_cache = {1: "alpha", 2: "Inbox", 3: "beta"}
        bot.client._inbox_tag_id = 2
        result = bot._user_visible_tags()
        assert result == [(1, "alpha"), (3, "beta")]

    def test_user_visible_tags_sorted(self, bot):
        bot.client._tags_cache = {1: "zebra", 2: "apple", 3: "mango"}
        bot.client._inbox_tag_id = None
        result = bot._user_visible_tags()
        assert [name for _, name in result] == ["apple", "mango", "zebra"]

    def test_format_document_list_basic(self, bot):
        docs = [_make_doc()]
        text = PaperlessBot._format_document_list(docs)
        assert "<b>Test Doc</b>" in text
        assert "Corr: ACME" in text
        assert "Type: Bill" in text
        assert "Tags: invoice" in text

    def test_format_document_list_no_metadata(self, bot):
        doc = Document(
            id=42,
            title="Test Doc",
            correspondent=None,
            document_type=None,
            tags=[],
            created="2025-01-15",
            added="2025-01-15",
        )
        text = PaperlessBot._format_document_list([doc])
        assert "<b>Test Doc</b>" in text
        assert "Corr:" not in text
        assert "Type:" not in text
        assert "Tags:" not in text

    def test_format_document_list_with_content(self, bot):
        doc = _make_doc(content="This is the snippet content")
        text = PaperlessBot._format_document_list([doc])
        assert "This is the snippet content" in text

    def test_format_document_list_escapes_content_html(self, bot):
        doc = _make_doc(content="content <b>bold</b> & more")
        text = PaperlessBot._format_document_list([doc])
        # HTML in content must be escaped so it cannot break the message
        assert "&lt;b&gt;bold&lt;/b&gt;" in text
        assert "<b>bold</b>" not in text


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


class TestCommandHandlers:
    async def test_cmd_start(self, bot):
        update = _make_update()
        await bot.cmd_start(update, MagicMock())
        update.message.reply_text.assert_awaited_once()
        call_args = update.message.reply_text.call_args
        assert "Paperless-NGX Bot" in call_args.args[0]
        assert call_args.kwargs["parse_mode"] == ParseMode.HTML

    async def test_cmd_start_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.cmd_start(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_help_delegates_to_start(self, bot):
        update = _make_update()
        ctx = MagicMock()
        with patch.object(bot, "cmd_start", new_callable=AsyncMock) as mock_start:
            await bot.cmd_help(update, ctx)
            mock_start.assert_awaited_once_with(update, ctx)

    async def test_cmd_help_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.cmd_help(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_inbox_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.cmd_inbox(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_stats_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.cmd_stats(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_search_no_query(self, bot):
        update = _make_update()
        ctx = MagicMock()
        ctx.args = []
        await bot.cmd_search(update, ctx)
        update.message.reply_text.assert_awaited_once_with("Usage: /search <query>")

    async def test_cmd_search_with_query(self, bot):
        update = _make_update()
        ctx = MagicMock()
        ctx.args = ["test", "query"]
        with patch.object(bot, "_do_search", new_callable=AsyncMock) as mock_search:
            await bot.cmd_search(update, ctx)
            mock_search.assert_awaited_once_with(update, ctx, "test query", page=1)

    async def test_cmd_search_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        ctx = MagicMock()
        ctx.args = ["query"]
        await bot.cmd_search(update, ctx)
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_recent_success(self, bot):
        update = _make_update()
        docs = [_make_doc()]
        bot.client.get_recent_documents = AsyncMock(return_value=docs)
        await bot.cmd_recent(update, MagicMock())
        update.message.reply_text.assert_awaited_once()
        call_args = update.message.reply_text.call_args
        assert "Recent Documents" in call_args.args[0]

    async def test_cmd_recent_empty(self, bot):
        update = _make_update()
        bot.client.get_recent_documents = AsyncMock(return_value=[])
        await bot.cmd_recent(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("No documents found.")

    async def test_cmd_recent_error(self, bot):
        update = _make_update()
        bot.client.get_recent_documents = AsyncMock(side_effect=Exception("API error"))
        await bot.cmd_recent(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("Failed to fetch recent documents.")

    async def test_cmd_recent_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.cmd_recent(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_cmd_inbox_success(self, bot):
        update = _make_update()
        docs = [_make_doc()]
        bot.client.get_inbox_documents = AsyncMock(return_value=(docs, 1))
        await bot.cmd_inbox(update, MagicMock())
        call_args = update.message.reply_text.call_args
        assert "Inbox" in call_args.args[0]

    async def test_cmd_inbox_empty(self, bot):
        update = _make_update()
        bot.client.get_inbox_documents = AsyncMock(return_value=([], 0))
        await bot.cmd_inbox(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("Inbox is empty.")

    async def test_cmd_inbox_error(self, bot):
        update = _make_update()
        bot.client.get_inbox_documents = AsyncMock(side_effect=Exception("fail"))
        await bot.cmd_inbox(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("Failed to fetch inbox documents.")

    async def test_cmd_stats_success(self, bot):
        update = _make_update()
        bot.client.get_statistics = AsyncMock(
            return_value={
                "documents_total": 100,
                "documents_inbox": 5,
                "correspondents_total": 10,
                "tags_total": 20,
                "document_types_total": 8,
            }
        )
        await bot.cmd_stats(update, MagicMock())
        call_args = update.message.reply_text.call_args
        assert "100" in call_args.args[0]
        assert "Statistics" in call_args.args[0]

    async def test_cmd_stats_error(self, bot):
        update = _make_update()
        bot.client.get_statistics = AsyncMock(side_effect=Exception("fail"))
        await bot.cmd_stats(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("Failed to fetch statistics.")


# ---------------------------------------------------------------------------
# Document / photo upload handlers
# ---------------------------------------------------------------------------


class TestUploadHandlers:
    async def test_handle_document_success(self, bot):
        update = _make_update()
        doc_mock = MagicMock()
        doc_mock.file_id = "file-123"
        doc_mock.file_name = "test.pdf"
        doc_mock.file_size = 1234
        update.message.document = doc_mock
        update.message.reply_text = AsyncMock(return_value=MagicMock())

        ctx = MagicMock()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"data"))
        ctx.bot.get_file = AsyncMock(return_value=tg_file)

        with patch.object(bot, "_process_upload", new_callable=AsyncMock) as mock_upload:
            await bot.handle_document(update, ctx)
            mock_upload.assert_awaited_once()

    async def test_handle_document_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.handle_document(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_handle_document_exception(self, bot):
        update = _make_update()
        doc_mock = MagicMock()
        doc_mock.file_id = "file-123"
        doc_mock.file_name = "test.pdf"
        doc_mock.file_size = 1234
        update.message.document = doc_mock
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        ctx = MagicMock()
        ctx.bot.get_file = AsyncMock(side_effect=Exception("network fail"))

        await bot.handle_document(update, ctx)
        # _safe_edit should be called with failure message
        status_msg.edit_text.assert_awaited()

    async def test_handle_photo_success(self, bot):
        update = _make_update()
        photo_mock = MagicMock()
        photo_mock.file_id = "photo-123"
        update.message.photo = [MagicMock(), photo_mock]  # last = highest res
        update.message.reply_text = AsyncMock(return_value=MagicMock())

        ctx = MagicMock()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"photo-data"))
        ctx.bot.get_file = AsyncMock(return_value=tg_file)

        with patch.object(bot, "_process_upload", new_callable=AsyncMock) as mock_upload:
            await bot.handle_photo(update, ctx)
            mock_upload.assert_awaited_once()
            # Check filename format - positional args: chat_id, status_msg, file_bytes, filename
            filename = mock_upload.call_args.args[3]
            assert filename.startswith("photo_")
            assert filename.endswith(".jpg")

    async def test_handle_photo_unauthorized(self, bot):
        update = _make_update(user_id=99999)
        bot.config.telegram_allowed_users = {12345}
        await bot.handle_photo(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_handle_photo_exception(self, bot):
        update = _make_update()
        photo_mock = MagicMock()
        photo_mock.file_id = "photo-123"
        update.message.photo = [photo_mock]
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        ctx = MagicMock()
        ctx.bot.get_file = AsyncMock(side_effect=Exception("fail"))

        await bot.handle_photo(update, ctx)
        status_msg.edit_text.assert_awaited()


# ---------------------------------------------------------------------------
# _process_upload
# ---------------------------------------------------------------------------


class TestProcessUpload:
    async def test_success(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(return_value=TaskResult(status="success", doc_id=42))
        bot.client.get_document = AsyncMock(return_value=_make_doc(doc_id=42))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")

        assert (100, 42) in bot.pending_uploads

    async def test_duplicate_with_id(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(
            return_value=TaskResult(status="duplicate", doc_id=10, message="duplicate of #10")
        )
        bot.client.get_document = AsyncMock(return_value=_make_doc(doc_id=10, title="Existing"))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")
        # Should show duplicate message
        assert status_msg.edit_text.await_count >= 2

    async def test_duplicate_with_id_fetch_fails(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(return_value=TaskResult(status="duplicate", doc_id=10, message="dup"))
        bot.client.get_document = AsyncMock(side_effect=Exception("not found"))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")
        # Should still show a duplicate message even though fetch failed
        assert status_msg.edit_text.await_count >= 2

    async def test_duplicate_without_id(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(return_value=TaskResult(status="duplicate", doc_id=None, message="dup"))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")
        last_call = status_msg.edit_text.call_args_list[-1]
        assert "already exists" in last_call.args[0]

    async def test_failed(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(return_value=TaskResult(status="failed", message="OCR failed"))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")
        last_call = status_msg.edit_text.call_args_list[-1]
        assert "failed" in last_call.args[0].lower()

    async def test_timeout(self, bot):
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()

        bot.client.upload_document = AsyncMock(return_value="task-abc")
        bot.client.wait_for_task = AsyncMock(return_value=TaskResult(status="timeout"))

        await bot._process_upload(100, status_msg, b"data", "test.pdf")
        last_call = status_msg.edit_text.call_args_list[-1]
        assert "timed out" in last_call.args[0].lower()


# ---------------------------------------------------------------------------
# Text message handler
# ---------------------------------------------------------------------------


class TestHandleText:
    async def test_search_on_text(self, bot):
        update = _make_update(text="invoice query")
        ctx = MagicMock()
        with patch.object(bot, "_do_search", new_callable=AsyncMock) as mock_search:
            await bot.handle_text(update, ctx)
            mock_search.assert_awaited_once_with(update, ctx, "invoice query", page=1)

    async def test_empty_text_ignored(self, bot):
        update = _make_update(text="   ")
        ctx = MagicMock()
        with patch.object(bot, "_do_search", new_callable=AsyncMock) as mock_search:
            await bot.handle_text(update, ctx)
            mock_search.assert_not_awaited()

    async def test_unauthorized(self, bot):
        update = _make_update(user_id=99999, text="query")
        bot.config.telegram_allowed_users = {12345}
        await bot.handle_text(update, MagicMock())
        update.message.reply_text.assert_awaited_once_with("You are not authorized to use this bot.")

    async def test_pending_create_tag(self, bot):
        update = _make_update(chat_id=100, text="New Tag Name")
        bot.pending_creates[100] = {"type": "tag", "doc_id": 42, "ts": time.monotonic()}
        with patch.object(bot, "_create_new_item", new_callable=AsyncMock) as mock_create:
            await bot.handle_text(update, MagicMock())
            mock_create.assert_awaited_once()
            # pending_creates should be cleared
            assert 100 not in bot.pending_creates


# ---------------------------------------------------------------------------
# _create_new_item
# ---------------------------------------------------------------------------


class TestCreateNewItem:
    async def test_create_tag(self, bot):
        update = _make_update(chat_id=100)
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client.create_tag = AsyncMock(return_value=MagicMock(id=5, name="NewTag"))
        bot.client._tags_cache = {1: "existing"}
        bot.client._inbox_tag_id = None

        await bot._create_new_item(update, MagicMock(), 100, "NewTag", {"type": "tag", "doc_id": 42})
        bot.client.create_tag.assert_awaited_once_with("NewTag")
        # Tag should be auto-selected on the document the prompt was for
        assert 5 in bot.pending_uploads[(100, 42)]["selected_tags"]

    async def test_create_correspondent(self, bot):
        update = _make_update(chat_id=100)
        bot.client.create_correspondent = AsyncMock(return_value=MagicMock(id=3, name="NewCorr"))
        bot.client.update_document = AsyncMock(return_value=_make_doc())

        await bot._create_new_item(update, MagicMock(), 100, "NewCorr", {"type": "corr", "doc_id": 42})
        bot.client.create_correspondent.assert_awaited_once_with("NewCorr")
        bot.client.update_document.assert_awaited_once_with(42, correspondent=3)

    async def test_create_document_type(self, bot):
        update = _make_update(chat_id=100)
        bot.client.create_document_type = AsyncMock(return_value=MagicMock(id=7, name="NewType"))
        bot.client.update_document = AsyncMock(return_value=_make_doc())

        await bot._create_new_item(update, MagicMock(), 100, "NewType", {"type": "dtype", "doc_id": 42})
        bot.client.create_document_type.assert_awaited_once_with("NewType")
        bot.client.update_document.assert_awaited_once_with(42, document_type=7)

    async def test_create_tag_error(self, bot):
        update = _make_update(chat_id=100)
        bot.client.create_tag = AsyncMock(side_effect=Exception("API error"))

        await bot._create_new_item(update, MagicMock(), 100, "BadTag", {"type": "tag", "doc_id": 42})
        update.message.reply_text.assert_awaited()
        call_args = update.message.reply_text.call_args
        assert "Failed" in call_args.args[0]


# ---------------------------------------------------------------------------
# _do_search
# ---------------------------------------------------------------------------


class TestDoSearch:
    async def test_search_with_results(self, bot):
        update = _make_update(chat_id=100)
        ctx = MagicMock()
        send_msg = MagicMock()
        send_msg.edit_text = AsyncMock()
        ctx.bot.send_message = AsyncMock(return_value=send_msg)

        docs = [_make_doc()]
        bot.client.search_documents = AsyncMock(return_value=(docs, 1))

        await bot._do_search(update, ctx, "invoice", page=1)
        assert bot.search_queries[100] == "invoice"

    async def test_search_no_results(self, bot):
        update = _make_update(chat_id=100)
        ctx = MagicMock()
        send_msg = MagicMock()
        send_msg.edit_text = AsyncMock()
        ctx.bot.send_message = AsyncMock(return_value=send_msg)

        bot.client.search_documents = AsyncMock(return_value=([], 0))

        await bot._do_search(update, ctx, "nonexistent", page=1)

    async def test_search_error(self, bot):
        update = _make_update(chat_id=100)
        ctx = MagicMock()
        send_msg = MagicMock()
        send_msg.edit_text = AsyncMock()
        ctx.bot.send_message = AsyncMock(return_value=send_msg)

        bot.client.search_documents = AsyncMock(side_effect=Exception("API error"))

        await bot._do_search(update, ctx, "fail", page=1)


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------


class TestCallbackHandler:
    async def test_unauthorized_callback(self, bot):
        update = _make_callback_update(user_id=99999, data="dl:42")
        bot.config.telegram_allowed_users = {12345}
        await bot.handle_callback(update, MagicMock())
        update.callback_query.answer.assert_awaited_once()

    async def test_meta_tags_callback(self, bot):
        update = _make_callback_update(data="meta:tags:42")
        bot.client._ensure_cache = AsyncMock()
        bot.client._tags_cache = {1: "tag1", 2: "tag2"}
        bot.client._inbox_tag_id = None
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_text.assert_awaited_once()

    async def test_meta_corr_callback(self, bot):
        update = _make_callback_update(data="meta:corr:42")
        bot.client._ensure_cache = AsyncMock()
        bot.client._correspondents_cache = {1: "ACME"}
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_text.assert_awaited_once()

    async def test_meta_dtype_callback(self, bot):
        update = _make_callback_update(data="meta:dtype:42")
        bot.client._ensure_cache = AsyncMock()
        bot.client._doc_types_cache = {1: "Bill"}
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_text.assert_awaited_once()

    async def test_meta_done_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="meta:done:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client.remove_inbox_tag = AsyncMock()
        await bot.handle_callback(update, MagicMock())
        assert (100, 42) not in bot.pending_uploads
        bot.client.remove_inbox_tag.assert_awaited_once_with(42)

    async def test_meta_done_remove_inbox_disabled(self, bot):
        update = _make_callback_update(chat_id=100, data="meta:done:42")
        bot.config.remove_inbox_on_done = False
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client.remove_inbox_tag = AsyncMock()
        await bot.handle_callback(update, MagicMock())
        bot.client.remove_inbox_tag.assert_not_awaited()

    async def test_meta_done_remove_inbox_error(self, bot):
        update = _make_callback_update(chat_id=100, data="meta:done:42")
        bot.pending_uploads[100] = {"doc_id": 42}
        bot.client.remove_inbox_tag = AsyncMock(side_effect=Exception("fail"))
        # Should not raise
        await bot.handle_callback(update, MagicMock())

    async def test_tag_toggle_check(self, bot):
        update = _make_callback_update(chat_id=100, data="tag:o:5:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {5: "invoice"}
        bot.client._inbox_tag_id = None
        await bot.handle_callback(update, MagicMock())
        assert 5 in bot.pending_uploads[(100, 42)]["selected_tags"]

    async def test_tag_toggle_uncheck(self, bot):
        update = _make_callback_update(chat_id=100, data="tag:x:5:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": {5}, "ts": time.monotonic()}
        bot.client._tags_cache = {5: "invoice"}
        bot.client._inbox_tag_id = None
        await bot.handle_callback(update, MagicMock())
        assert 5 not in bot.pending_uploads[(100, 42)]["selected_tags"]

    async def test_tag_toggle_unknown_tag_id(self, bot):
        """Tag ID not in visible tags triggers ValueError branch."""
        update = _make_callback_update(chat_id=100, data="tag:o:999:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {5: "invoice"}  # 999 not in cache
        bot.client._inbox_tag_id = None
        await bot.handle_callback(update, MagicMock())
        # Should fall back to page 0
        assert 999 in bot.pending_uploads[(100, 42)]["selected_tags"]

    async def test_tag_toggle_no_pending_restores_from_api(self, bot):
        update = _make_callback_update(chat_id=100, data="tag:o:5:42")
        bot.client._tags_cache = {5: "invoice"}
        bot.client._inbox_tag_id = None
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        await bot.handle_callback(update, MagicMock())
        # State restored from Paperless, toggle applied
        assert 5 in bot.pending_uploads[(100, 42)]["selected_tags"]

    async def test_tag_page_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="tagp:1:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {i: f"tag{i}" for i in range(20)}
        bot.client._inbox_tag_id = None
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_reply_markup.assert_awaited_once()

    async def test_tagok_with_tags(self, bot):
        update = _make_callback_update(chat_id=100, data="tagok:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": {1, 2}, "ts": time.monotonic()}
        bot.client._tags_cache = {1: "tag1", 2: "tag2"}
        bot.client._inbox_tag_id = None
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        bot.client.update_document = AsyncMock(return_value=_make_doc())
        await bot.handle_callback(update, MagicMock())
        bot.client.update_document.assert_awaited_once_with(42, tags=[1, 2])

    async def test_tagok_no_tags(self, bot):
        update = _make_callback_update(chat_id=100, data="tagok:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {}
        bot.client._inbox_tag_id = None
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        bot.client.update_document = AsyncMock()
        await bot.handle_callback(update, MagicMock())
        bot.client.update_document.assert_not_awaited()
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "No tags selected" in call_text

    async def test_tagok_error(self, bot):
        update = _make_callback_update(chat_id=100, data="tagok:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": {1}, "ts": time.monotonic()}
        bot.client._tags_cache = {1: "tag1"}
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        bot.client.update_document = AsyncMock(side_effect=Exception("fail"))
        await bot.handle_callback(update, MagicMock())
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "Failed" in call_text

    async def test_corr_select(self, bot):
        update = _make_callback_update(chat_id=100, data="corr:3:42")
        bot.client.update_document = AsyncMock(return_value=_make_doc())
        bot.client._correspondents_cache = {3: "ACME"}
        await bot.handle_callback(update, MagicMock())
        bot.client.update_document.assert_awaited_once_with(42, correspondent=3)

    async def test_corr_skip(self, bot):
        update = _make_callback_update(data="corr:skip:42")
        await bot.handle_callback(update, MagicMock())
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "skipped" in call_text.lower()

    async def test_corr_select_error(self, bot):
        update = _make_callback_update(data="corr:3:42")
        bot.client.update_document = AsyncMock(side_effect=Exception("fail"))
        await bot.handle_callback(update, MagicMock())
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "Failed" in call_text

    async def test_dtype_select(self, bot):
        update = _make_callback_update(data="dtype:7:42")
        bot.client.update_document = AsyncMock(return_value=_make_doc())
        bot.client._doc_types_cache = {7: "Invoice"}
        await bot.handle_callback(update, MagicMock())
        bot.client.update_document.assert_awaited_once_with(42, document_type=7)

    async def test_corrp_pagination(self, bot):
        update = _make_callback_update(data="corrp:1:42")
        bot.client._correspondents_cache = {i: f"corr{i}" for i in range(20)}
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_reply_markup.assert_awaited_once()

    async def test_dtypep_pagination(self, bot):
        update = _make_callback_update(data="dtypep:1:42")
        bot.client._doc_types_cache = {i: f"type{i}" for i in range(20)}
        await bot.handle_callback(update, MagicMock())
        update.callback_query.edit_message_reply_markup.assert_awaited_once()

    async def test_newtag_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="newtag:42")
        await bot.handle_callback(update, MagicMock())
        assert 100 in bot.pending_creates
        assert bot.pending_creates[100]["type"] == "tag"

    async def test_newcorr_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="newcorr:42")
        await bot.handle_callback(update, MagicMock())
        assert bot.pending_creates[100]["type"] == "corr"

    async def test_newdtype_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="newdtype:42")
        await bot.handle_callback(update, MagicMock())
        assert bot.pending_creates[100]["type"] == "dtype"

    async def test_cancel_create_tag(self, bot):
        update = _make_callback_update(chat_id=100, data="ccr:tag:42")
        bot.pending_creates[100] = {"type": "tag", "doc_id": 42}
        bot.client._ensure_cache = AsyncMock()
        bot.client._tags_cache = {1: "tag1"}
        bot.client._inbox_tag_id = None
        bot.pending_uploads[(100, 42)] = {"selected_tags": set(), "ts": time.monotonic()}
        await bot.handle_callback(update, MagicMock())
        assert 100 not in bot.pending_creates

    async def test_cancel_create_corr(self, bot):
        update = _make_callback_update(chat_id=100, data="ccr:corr:42")
        bot.pending_creates[100] = {"type": "corr", "doc_id": 42}
        bot.client._ensure_cache = AsyncMock()
        bot.client._correspondents_cache = {1: "ACME"}
        await bot.handle_callback(update, MagicMock())
        assert 100 not in bot.pending_creates

    async def test_cancel_create_dtype(self, bot):
        update = _make_callback_update(chat_id=100, data="ccr:dtype:42")
        bot.pending_creates[100] = {"type": "dtype", "doc_id": 42}
        bot.client._ensure_cache = AsyncMock()
        bot.client._doc_types_cache = {1: "Bill"}
        await bot.handle_callback(update, MagicMock())
        assert 100 not in bot.pending_creates

    async def test_rev_callback(self, bot):
        update = _make_callback_update(data="rev:42")
        bot.client.remove_inbox_tag = AsyncMock()
        bot.client.get_document = AsyncMock(return_value=_make_doc(doc_id=42))
        await bot.handle_callback(update, MagicMock())
        bot.client.remove_inbox_tag.assert_awaited_once_with(42)

    async def test_rev_callback_error(self, bot):
        update = _make_callback_update(data="rev:42")
        bot.client.remove_inbox_tag = AsyncMock(side_effect=Exception("fail"))
        await bot.handle_callback(update, MagicMock())
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "Failed" in call_text

    async def test_dl_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="dl:42")
        ctx = MagicMock()
        ctx.bot.send_document = AsyncMock()
        bot.client.download_document = AsyncMock(return_value=(b"pdf-data", "invoice.pdf"))
        await bot.handle_callback(update, ctx)
        ctx.bot.send_document.assert_awaited_once()

    async def test_dl_callback_too_large(self, bot):
        from paperless_bot.api.client import DocumentTooLargeError

        update = _make_callback_update(chat_id=100, data="dl:42")
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()
        bot.client.download_document = AsyncMock(
            side_effect=DocumentTooLargeError(TELEGRAM_FILE_LIMIT + 1, TELEGRAM_FILE_LIMIT)
        )
        await bot.handle_callback(update, ctx)
        # The size cap is enforced by the client (before buffering the file)
        assert bot.client.download_document.call_args.kwargs["max_bytes"] == TELEGRAM_FILE_LIMIT
        ctx.bot.send_message.assert_awaited_once()
        assert "too large" in ctx.bot.send_message.call_args.kwargs["text"].lower()

    async def test_dl_callback_error(self, bot):
        update = _make_callback_update(chat_id=100, data="dl:42")
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()
        bot.client.download_document = AsyncMock(side_effect=Exception("fail"))
        await bot.handle_callback(update, ctx)
        ctx.bot.send_message.assert_awaited_once()

    async def test_search_page_callback(self, bot):
        update = _make_callback_update(chat_id=100, data="sp:2")
        bot.search_queries[100] = "invoice"
        docs = [_make_doc()]
        bot.client.search_documents = AsyncMock(return_value=(docs, 15))
        await bot.handle_callback(update, MagicMock())

    async def test_search_page_expired(self, bot):
        update = _make_callback_update(chat_id=100, data="sp:2")
        # No search query stored
        await bot.handle_callback(update, MagicMock())
        call_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "expired" in call_text.lower()

    async def test_search_page_error(self, bot):
        update = _make_callback_update(chat_id=100, data="sp:2")
        bot.search_queries[100] = "invoice"
        bot.client.search_documents = AsyncMock(side_effect=Exception("fail"))
        await bot.handle_callback(update, MagicMock())


# ---------------------------------------------------------------------------
# create_bot and _post_init
# ---------------------------------------------------------------------------


class TestCreateBot:
    def test_create_bot_returns_application(self, config):
        app = create_bot(config)
        assert app is not None

    async def test_post_init(self):
        app = MagicMock()
        app.bot.set_my_commands = AsyncMock()
        await _post_init(app)
        app.bot.set_my_commands.assert_awaited_once()


# ---------------------------------------------------------------------------
# _error_handler
# ---------------------------------------------------------------------------


class TestErrorHandler:
    async def test_network_error_logged_as_warning(self, caplog):
        context = MagicMock()
        context.error = NetworkError("Server disconnected")
        with caplog.at_level("WARNING", logger="paperless_bot.bot.handlers"):
            await _error_handler(None, context)
        assert "will retry" in caplog.text
        assert "Traceback" not in caplog.text

    async def test_timeout_error_logged_as_warning(self, caplog):
        context = MagicMock()
        context.error = TimedOut("timed out")
        with caplog.at_level("WARNING", logger="paperless_bot.bot.handlers"):
            await _error_handler(None, context)
        assert "will retry" in caplog.text

    async def test_other_error_logged_as_error(self, caplog):
        context = MagicMock()
        context.error = ValueError("boom")
        with caplog.at_level("ERROR", logger="paperless_bot.bot.handlers"):
            await _error_handler("some-update", context)
        assert "Unhandled error" in caplog.text


# ---------------------------------------------------------------------------
# v0.7.0 hardening behaviors
# ---------------------------------------------------------------------------


class TestHtmlEscaping:
    def test_h_escapes_html(self):
        from paperless_bot.bot.handlers import _h

        assert _h("<b>x</b> & y") == "&lt;b&gt;x&lt;/b&gt; &amp; y"

    def test_h_leaves_markdown_chars_alone(self):
        from paperless_bot.bot.handlers import _h

        assert _h("tax_2024 *bold* `code`") == "tax_2024 *bold* `code`"


class TestSafeQueryEdit:
    async def test_swallows_not_modified(self, caplog):
        from paperless_bot.bot.handlers import _safe_query_edit

        query = MagicMock()
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Message is not modified"))
        with caplog.at_level("WARNING", logger="paperless_bot.bot.handlers"):
            assert await _safe_query_edit(query, "same text") is False
        assert "not modified" not in caplog.text

    async def test_logs_other_bad_request(self, caplog):
        from paperless_bot.bot.handlers import _safe_query_edit

        query = MagicMock()
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Can't parse entities"))
        with caplog.at_level("WARNING", logger="paperless_bot.bot.handlers"):
            assert await _safe_query_edit(query, "bad") is False
        assert "BadRequest" in caplog.text

    async def test_network_error(self):
        from paperless_bot.bot.handlers import _safe_query_edit

        query = MagicMock()
        query.edit_message_text = AsyncMock(side_effect=NetworkError("boom"))
        assert await _safe_query_edit(query, "text") is False

    async def test_reply_markup_only(self):
        from paperless_bot.bot.handlers import _safe_query_edit

        query = MagicMock()
        query.edit_message_reply_markup = AsyncMock()
        assert await _safe_query_edit(query, reply_markup=None) is True
        query.edit_message_reply_markup.assert_awaited_once()


class TestOversizeAndFilename:
    async def test_document_over_20mb_rejected(self, bot):
        from paperless_bot.bot.handlers import TELEGRAM_DOWNLOAD_LIMIT

        update = _make_update()
        doc_mock = MagicMock()
        doc_mock.file_size = TELEGRAM_DOWNLOAD_LIMIT + 1
        update.message.document = doc_mock
        ctx = MagicMock()
        ctx.bot.get_file = AsyncMock()

        await bot.handle_document(update, ctx)
        ctx.bot.get_file.assert_not_awaited()
        msg = update.message.reply_text.call_args.args[0]
        assert "20MB" in msg

    async def test_document_without_filename_gets_fallback(self, bot):
        update = _make_update()
        doc_mock = MagicMock()
        doc_mock.file_id = "file-123"
        doc_mock.file_name = None
        doc_mock.file_size = 1234
        update.message.document = doc_mock
        update.message.date = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)
        update.message.reply_text = AsyncMock(return_value=MagicMock())

        ctx = MagicMock()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"data"))
        ctx.bot.get_file = AsyncMock(return_value=tg_file)

        with patch.object(bot, "_process_upload", new_callable=AsyncMock) as mock_upload:
            await bot.handle_document(update, ctx)
            filename = mock_upload.call_args.args[3]
            assert filename == "document_20260811_120000.pdf"


class TestStaleKeyboards:
    async def test_tagok_restored_state_confirms_as_noop(self, bot):
        """A keyboard that outlived memory restores from Paperless and never strips tags."""
        update = _make_callback_update(chat_id=100, data="tagok:42")
        # Another document's state exists; nothing for (100, 42)
        bot.pending_uploads[(100, 99)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {2: "old", 9: "Inbox"}
        bot.client._inbox_tag_id = 9
        bot.client.get_document_tag_ids = AsyncMock(return_value=[2, 9])
        bot.client.update_document = AsyncMock()
        await bot.handle_callback(update, MagicMock())
        # Selection was seeded from current tags, so confirm is a no-op PATCH-wise
        bot.client.update_document.assert_not_awaited()
        # And doc 99's state was untouched
        assert bot.pending_uploads[(100, 99)]["selected_tags"] == set()

    async def test_tag_toggle_two_documents_stay_independent(self, bot):
        update = _make_callback_update(chat_id=100, data="tag:o:5:42")
        bot.pending_uploads[(100, 99)] = {"selected_tags": set(), "ts": time.monotonic()}
        bot.client._tags_cache = {5: "invoice"}
        bot.client._inbox_tag_id = None
        bot.client.get_document_tag_ids = AsyncMock(return_value=[])
        await bot.handle_callback(update, MagicMock())
        assert 5 in bot.pending_uploads[(100, 42)]["selected_tags"]
        assert bot.pending_uploads[(100, 99)]["selected_tags"] == set()

    async def test_tagok_preserves_inbox_tag(self, bot):
        update = _make_callback_update(chat_id=100, data="tagok:42")
        bot.pending_uploads[(100, 42)] = {"selected_tags": {1}, "ts": time.monotonic()}
        bot.client._tags_cache = {1: "tag1", 2: "old", 9: "Inbox"}
        bot.client._inbox_tag_id = 9
        # Document currently has the inbox tag (9) and an unchecked visible tag (2)
        bot.client.get_document_tag_ids = AsyncMock(return_value=[9, 2])
        bot.client.update_document = AsyncMock(return_value=_make_doc())
        await bot.handle_callback(update, MagicMock())
        # Inbox tag kept, unchecked visible tag 2 removed, selection 1 added
        bot.client.update_document.assert_awaited_once_with(42, tags=[1, 9])


class TestPendingCreateTTL:
    async def test_expired_pending_create_notifies_instead_of_searching(self, bot):
        update = _make_update(chat_id=100, text="Invoices")
        bot.pending_creates[100] = {"type": "tag", "doc_id": 42, "ts": time.monotonic() - 3600}
        with (
            patch.object(bot, "_create_new_item", new_callable=AsyncMock) as mock_create,
            patch.object(bot, "_do_search", new_callable=AsyncMock) as mock_search,
        ):
            await bot.handle_text(update, MagicMock())
            mock_create.assert_not_awaited()
            mock_search.assert_not_awaited()
        msg = update.message.reply_text.call_args.args[0]
        assert "expired" in msg
        assert 100 not in bot.pending_creates

    async def test_upload_clears_pending_create(self, bot):
        update = _make_update(chat_id=100)
        doc_mock = MagicMock()
        doc_mock.file_id = "f"
        doc_mock.file_name = "a.pdf"
        doc_mock.file_size = 10
        update.message.document = doc_mock
        update.message.reply_text = AsyncMock(return_value=MagicMock())
        bot.pending_creates[100] = {"type": "tag", "doc_id": 42, "ts": time.monotonic()}
        ctx = MagicMock()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"d"))
        ctx.bot.get_file = AsyncMock(return_value=tg_file)
        with patch.object(bot, "_process_upload", new_callable=AsyncMock):
            await bot.handle_document(update, ctx)
        assert 100 not in bot.pending_creates


class TestStateEviction:
    def test_pending_uploads_evict_oldest(self, bot):
        from paperless_bot.bot.handlers import MAX_PENDING_ENTRIES

        for i in range(MAX_PENDING_ENTRIES):
            bot.pending_uploads[(1, i)] = {"selected_tags": set(), "ts": float(i)}
        bot._remember_pending(1, 9999, {7})
        assert (1, 0) not in bot.pending_uploads  # oldest evicted
        assert (1, 9999) in bot.pending_uploads
        assert len(bot.pending_uploads) == MAX_PENDING_ENTRIES

    async def test_search_queries_evict_oldest(self, bot):
        from paperless_bot.bot.handlers import MAX_SEARCH_ENTRIES

        for i in range(MAX_SEARCH_ENTRIES):
            bot.search_queries[i] = f"q{i}"
        update = _make_update(chat_id=99999, text="new query")
        ctx = MagicMock()
        status_msg = MagicMock()
        status_msg.edit_text = AsyncMock()
        ctx.bot.send_message = AsyncMock(return_value=status_msg)
        bot.client.search_documents = AsyncMock(return_value=([], 0))
        await bot._do_search(update, ctx, "new query", page=1)
        assert 0 not in bot.search_queries
        assert bot.search_queries[99999] == "new query"


class TestRestoreFailure:
    async def test_toggle_degrades_when_paperless_down(self, bot):
        update = _make_callback_update(chat_id=100, data="tag:o:5:42")
        bot.client.get_document_tag_ids = AsyncMock(side_effect=Exception("down"))
        await bot.handle_callback(update, MagicMock())
        msg = update.callback_query.edit_message_text.call_args.args[0]
        assert "Couldn't reach Paperless" in msg
        assert (100, 42) not in bot.pending_uploads

    async def test_confirm_degrades_when_paperless_down(self, bot):
        update = _make_callback_update(chat_id=100, data="tagok:42")
        bot.client.get_document_tag_ids = AsyncMock(side_effect=Exception("down"))
        bot.client.update_document = AsyncMock()
        await bot.handle_callback(update, MagicMock())
        bot.client.update_document.assert_not_awaited()
        msg = update.callback_query.edit_message_text.call_args.args[0]
        assert "Couldn't reach Paperless" in msg

    async def test_new_tag_created_but_restore_fails(self, bot):
        update = _make_update(chat_id=100)
        bot.client.create_tag = AsyncMock(return_value=MagicMock(id=5, name="NewTag"))
        bot.client.get_document_tag_ids = AsyncMock(side_effect=Exception("down"))
        await bot._create_new_item(update, MagicMock(), 100, "NewTag", {"type": "tag", "doc_id": 42})
        msg = update.message.reply_text.call_args.args[0]
        assert "created" in msg and "couldn't be reached" in msg
