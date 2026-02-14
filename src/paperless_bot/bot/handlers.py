"""
Telegram bot handlers for Paperless-NGX management.
"""

import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from paperless_bot.api.client import PaperlessClient
from paperless_bot.bot.keyboards import (
    build_document_list_keyboard,
    build_metadata_keyboard,
    build_search_results_keyboard,
    build_single_select_keyboard,
    build_tag_selection_keyboard,
)
from paperless_bot.config import Config

logger = logging.getLogger(__name__)

# Telegram bot API file size limit: 50 MB
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024

# Bot commands shown in Telegram's command menu
BOT_COMMANDS = [
    BotCommand("search", "Search documents"),
    BotCommand("recent", "Recently added documents"),
    BotCommand("inbox", "Documents in inbox"),
    BotCommand("stats", "Paperless statistics"),
    BotCommand("help", "Show help message"),
]


async def _safe_edit(msg: Message, text: str, **kwargs) -> bool:
    """Edit a Telegram message, swallowing common failures."""
    try:
        await msg.edit_text(text, **kwargs)
        return True
    except BadRequest as exc:
        logger.warning(f"Telegram edit failed (BadRequest): {exc}")
        return False
    except TimedOut:
        logger.warning("Telegram edit timed out")
        return False
    except NetworkError as exc:
        logger.warning(f"Telegram edit network error: {exc}")
        return False


class PaperlessBot:
    """Telegram bot for Paperless-NGX document management."""

    def __init__(self, config: Config):
        self.config = config
        self.client = PaperlessClient(config.paperless_url, config.paperless_token)

        # Per-chat state for post-upload metadata assignment
        # chat_id -> {"doc_id": int, "selected_tags": set[int]}
        self.pending_uploads: dict[int, dict] = {}

        # Per-chat search query (for pagination, since callback_data has 64-byte limit)
        self.search_queries: dict[int, str] = {}

        # Per-chat state for creating new metadata items
        # chat_id -> {"type": "tag"|"corr"|"dtype", "doc_id": int}
        self.pending_creates: dict[int, dict] = {}

    def _is_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot."""
        if not self.config.telegram_allowed_users:
            return True
        return user_id in self.config.telegram_allowed_users

    async def _check_auth(self, update: Update) -> bool:
        """Check authorization and send a message if denied."""
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return False
        return True

    def _document_url(self, doc_id: int) -> str:
        """Build a user-facing URL for a Paperless document."""
        return f"{self.config.paperless_public_url}/documents/{doc_id}/details"

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not await self._check_auth(update):
            return

        await update.message.reply_text(
            "*Paperless-NGX Bot*\n\n"
            "Send me a document or photo to upload it.\n"
            "Send any text to search your documents.\n\n"
            "Commands:\n"
            "/search <query> \u2014 Search documents\n"
            "/recent \u2014 Recently added documents\n"
            "/inbox \u2014 Documents in inbox\n"
            "/stats \u2014 Paperless statistics\n"
            "/help \u2014 Show this message",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not await self._check_auth(update):
            return
        await self.cmd_start(update, context)

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        if not await self._check_auth(update):
            return

        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /search <query>")
            return

        await self._do_search(update, context, query, page=1)

    async def cmd_recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recent command."""
        if not await self._check_auth(update):
            return

        try:
            documents = await self.client.get_recent_documents(self.config.max_search_results)
            if not documents:
                await update.message.reply_text("No documents found.")
                return

            text = "*Recent Documents*\n\n"
            text += self._format_document_list(documents)
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_document_list_keyboard(documents),
            )
        except Exception:
            logger.exception("Failed to fetch recent documents")
            await update.message.reply_text("Failed to fetch recent documents.")

    async def cmd_inbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /inbox command."""
        if not await self._check_auth(update):
            return

        try:
            documents, total = await self.client.get_inbox_documents(self.config.max_search_results)
            if not documents:
                await update.message.reply_text("Inbox is empty.")
                return

            text = f"*Inbox* ({total} documents)\n\n"
            text += self._format_document_list(documents)
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_document_list_keyboard(documents),
            )
        except Exception:
            logger.exception("Failed to fetch inbox")
            await update.message.reply_text("Failed to fetch inbox documents.")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        if not await self._check_auth(update):
            return

        try:
            stats = await self.client.get_statistics()
            text = (
                "*Paperless-NGX Statistics*\n\n"
                f"Documents: {stats.get('documents_total', 'N/A')}\n"
                f"In inbox: {stats.get('documents_inbox', 'N/A')}\n"
                f"Correspondents: {stats.get('correspondents_total', 'N/A')}\n"
                f"Tags: {stats.get('tags_total', 'N/A')}\n"
                f"Document types: {stats.get('document_types_total', 'N/A')}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            logger.exception("Failed to fetch statistics")
            await update.message.reply_text("Failed to fetch statistics.")

    # =========================================================================
    # DOCUMENT / PHOTO UPLOAD HANDLERS
    # =========================================================================

    async def _process_upload(self, chat_id: int, status_msg: Message, file_bytes: bytes, filename: str):
        """Upload file to Paperless and handle the task result (success, duplicate, failure, timeout)."""
        task_id = await self.client.upload_document(file_bytes, filename)
        await _safe_edit(status_msg, f"Uploaded! Processing... (task: `{task_id[:8]}`)", parse_mode=ParseMode.MARKDOWN)

        result = await self.client.wait_for_task(task_id, timeout=60)

        if result.status == "success" and result.doc_id:
            document = await self.client.get_document(result.doc_id)
            self.pending_uploads[chat_id] = {"doc_id": result.doc_id, "selected_tags": set()}
            await _safe_edit(
                status_msg,
                f"Document processed: *{document.title}*\n\nSet metadata?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_metadata_keyboard(result.doc_id),
            )

        elif result.status == "duplicate":
            if result.doc_id:
                try:
                    existing = await self.client.get_document(result.doc_id)
                    keyboard = InlineKeyboardMarkup(
                        [[InlineKeyboardButton(f"Download: {existing.title[:40]}", callback_data=f"dl:{existing.id}")]]
                    )
                    await _safe_edit(
                        status_msg,
                        f"Duplicate detected. This file already exists as *{existing.title}* (#{existing.id}).\n"
                        f"Added: {existing.added}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard,
                    )
                except Exception:
                    logger.warning("Could not fetch existing document #%s", result.doc_id)
                    await _safe_edit(
                        status_msg,
                        f"Duplicate detected. Existing document: #{result.doc_id}",
                    )
            else:
                await _safe_edit(
                    status_msg,
                    "Duplicate detected. This file already exists in Paperless.",
                )

        elif result.status == "failed":
            msg = result.message or "Unknown error"
            await _safe_edit(status_msg, f"Processing failed: {msg}")

        else:  # timeout
            await _safe_edit(status_msg, "Processing timed out. The document may still appear in Paperless shortly.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming document files."""
        if not await self._check_auth(update):
            return

        chat_id = update.effective_chat.id
        doc = update.message.document
        status_msg = await update.message.reply_text(
            f"Uploading `{doc.file_name}` to Paperless-NGX...", parse_mode=ParseMode.MARKDOWN
        )

        try:
            tg_file = await context.bot.get_file(doc.file_id)
            file_bytes = bytes(await tg_file.download_as_bytearray())
            await self._process_upload(chat_id, status_msg, file_bytes, doc.file_name)
        except Exception:
            logger.exception("Upload failed")
            await _safe_edit(status_msg, "Upload failed. Check logs.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos sent to the bot."""
        if not await self._check_auth(update):
            return

        chat_id = update.effective_chat.id
        photo = update.message.photo[-1]  # Highest resolution
        status_msg = await update.message.reply_text("Uploading photo to Paperless-NGX...")

        try:
            tg_file = await context.bot.get_file(photo.file_id)
            file_bytes = bytes(await tg_file.download_as_bytearray())
            filename = f"photo_{update.message.date.strftime('%Y%m%d_%H%M%S')}.jpg"
            await self._process_upload(chat_id, status_msg, file_bytes, filename)
        except Exception:
            logger.exception("Photo upload failed")
            await _safe_edit(status_msg, "Upload failed. Check logs.")

    # =========================================================================
    # TEXT MESSAGE HANDLER (search or new metadata name)
    # =========================================================================

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle plain text messages: either a new metadata name or a search query."""
        if not await self._check_auth(update):
            return

        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        if not text:
            return

        # Check if we're waiting for a new metadata item name
        pending = self.pending_creates.pop(chat_id, None)
        if pending:
            await self._create_new_item(update, context, chat_id, text, pending)
            return

        # Otherwise treat as search
        await self._do_search(update, context, text, page=1)

    async def _create_new_item(self, update, context, chat_id: int, name: str, pending: dict):
        """Create a new tag/correspondent/document type from user text input."""
        item_type = pending["type"]
        doc_id = pending["doc_id"]

        try:
            if item_type == "tag":
                tag = await self.client.create_tag(name)
                # Auto-select the new tag
                upload = self.pending_uploads.get(chat_id)
                if upload:
                    upload.setdefault("selected_tags", set()).add(tag.id)
                tags = sorted(self.client._tags_cache.items(), key=lambda x: x[1])
                selected = upload.get("selected_tags", set()) if upload else set()
                await update.message.reply_text(
                    f"Tag *{tag.name}* created and selected.\n\nSelect tags:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_tag_selection_keyboard(tags, selected, doc_id),
                )

            elif item_type == "corr":
                corr = await self.client.create_correspondent(name)
                await self.client.update_document(doc_id, correspondent=corr.id)
                await update.message.reply_text(
                    f"Correspondent *{corr.name}* created and assigned.\n\nContinue setting metadata?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_metadata_keyboard(doc_id),
                )

            elif item_type == "dtype":
                dt = await self.client.create_document_type(name)
                await self.client.update_document(doc_id, document_type=dt.id)
                await update.message.reply_text(
                    f"Document type *{dt.name}* created and assigned.\n\nContinue setting metadata?",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_metadata_keyboard(doc_id),
                )

        except Exception:
            logger.exception(f"Failed to create {item_type}: {name}")
            await update.message.reply_text(
                f"Failed to create {item_type}. Check logs.",
                reply_markup=build_metadata_keyboard(doc_id),
            )

    async def _do_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int):
        """Execute a document search and display results."""
        chat_id = update.effective_chat.id
        self.search_queries[chat_id] = query

        status_msg = await context.bot.send_message(
            chat_id=chat_id, text=f"Searching: `{query}`...", parse_mode=ParseMode.MARKDOWN
        )

        try:
            documents, total = await self.client.search_documents(
                query, page=page, page_size=self.config.max_search_results
            )
            if not documents:
                await _safe_edit(status_msg, f"No documents found for: `{query}`", parse_mode=ParseMode.MARKDOWN)
                return

            text = f"*Search: {query}* ({total} results)\n\n"
            text += self._format_document_list(documents)
            await _safe_edit(
                status_msg,
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_search_results_keyboard(documents, page, total, self.config.max_search_results),
            )
        except Exception:
            logger.exception(f"Search failed for: {query}")
            await _safe_edit(status_msg, "Search failed. Check logs.")

    # =========================================================================
    # CALLBACK QUERY HANDLER (button presses)
    # =========================================================================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()

        if not self._is_authorized(query.from_user.id):
            return

        chat_id = update.effective_chat.id
        data = query.data

        # Metadata menu
        if data.startswith("meta:"):
            await self._handle_metadata(update, context, chat_id, data)
        # Tag toggle
        elif data.startswith("tag:"):
            await self._handle_tag_toggle(update, context, chat_id, data)
        # Tag pagination
        elif data.startswith("tagp:"):
            await self._handle_tag_page(update, context, chat_id, data)
        # Tag confirm
        elif data.startswith("tagok:"):
            await self._handle_tag_confirm(update, context, chat_id, data)
        # New tag/correspondent/document type
        elif data.startswith("newtag:"):
            await self._handle_new_item(update, context, chat_id, data, "tag")
        elif data.startswith("newcorr:"):
            await self._handle_new_item(update, context, chat_id, data, "corr")
        elif data.startswith("newdtype:"):
            await self._handle_new_item(update, context, chat_id, data, "dtype")
        # Cancel new item creation
        elif data.startswith("ccr:"):
            await self._handle_cancel_create(update, context, chat_id, data)
        # Correspondent selection
        elif data.startswith("corr:"):
            await self._handle_single_select(update, context, chat_id, data, "correspondent")
        # Correspondent pagination
        elif data.startswith("corrp:"):
            await self._handle_select_page(update, context, chat_id, data, "corr")
        # Document type selection
        elif data.startswith("dtype:"):
            await self._handle_single_select(update, context, chat_id, data, "document_type")
        # Document type pagination
        elif data.startswith("dtypep:"):
            await self._handle_select_page(update, context, chat_id, data, "dtype")
        # Download
        elif data.startswith("dl:"):
            doc_id = int(data.split(":")[1])
            await self._handle_download(update, context, chat_id, doc_id)
        # Search pagination
        elif data.startswith("sp:"):
            page = int(data.split(":")[1])
            await self._handle_search_page(update, context, chat_id, page)

    # --- New item creation ---

    async def _handle_new_item(self, update, context, chat_id: int, data: str, item_type: str):
        """Prompt user to send the name for a new tag/correspondent/document type."""
        query = update.callback_query
        doc_id = int(data.split(":")[1])

        self.pending_creates[chat_id] = {"type": item_type, "doc_id": doc_id}

        labels = {"tag": "tag", "corr": "correspondent", "dtype": "document type"}
        label = labels[item_type]

        cancel_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Cancel", callback_data=f"ccr:{item_type}:{doc_id}")]]
        )
        await query.edit_message_text(
            f"Type the name for the new {label} as a text message:",
            reply_markup=cancel_keyboard,
        )

    async def _handle_cancel_create(self, update, context, chat_id: int, data: str):
        """Cancel pending new item creation and return to the selection screen."""
        query = update.callback_query
        parts = data.split(":")
        item_type = parts[1]
        doc_id = int(parts[2])

        # Clear pending state
        self.pending_creates.pop(chat_id, None)

        # Return to the appropriate selection screen
        await self.client._ensure_cache()
        if item_type == "tag":
            tags = sorted(self.client._tags_cache.items(), key=lambda x: x[1])
            selected = self.pending_uploads.get(chat_id, {}).get("selected_tags", set())
            await query.edit_message_text(
                "Select tags:",
                reply_markup=build_tag_selection_keyboard(tags, selected, doc_id),
            )
        elif item_type == "corr":
            correspondents = sorted(self.client._correspondents_cache.items(), key=lambda x: x[1])
            await query.edit_message_text(
                "Select correspondent:",
                reply_markup=build_single_select_keyboard(correspondents, "corr", doc_id),
            )
        elif item_type == "dtype":
            doc_types = sorted(self.client._doc_types_cache.items(), key=lambda x: x[1])
            await query.edit_message_text(
                "Select document type:",
                reply_markup=build_single_select_keyboard(doc_types, "dtype", doc_id),
            )

    # --- Metadata flow ---

    async def _handle_metadata(self, update, context, chat_id: int, data: str):
        """Handle metadata menu button presses."""
        query = update.callback_query
        parts = data.split(":")
        action = parts[1]
        doc_id = int(parts[2])

        if action == "tags":
            await self.client._ensure_cache()
            tags = sorted(self.client._tags_cache.items(), key=lambda x: x[1])
            selected = self.pending_uploads.get(chat_id, {}).get("selected_tags", set())
            await query.edit_message_text(
                "Select tags:",
                reply_markup=build_tag_selection_keyboard(tags, selected, doc_id),
            )

        elif action == "corr":
            await self.client._ensure_cache()
            correspondents = sorted(self.client._correspondents_cache.items(), key=lambda x: x[1])
            await query.edit_message_text(
                "Select correspondent:",
                reply_markup=build_single_select_keyboard(correspondents, "corr", doc_id),
            )

        elif action == "dtype":
            await self.client._ensure_cache()
            doc_types = sorted(self.client._doc_types_cache.items(), key=lambda x: x[1])
            await query.edit_message_text(
                "Select document type:",
                reply_markup=build_single_select_keyboard(doc_types, "dtype", doc_id),
            )

        elif action == "done":
            self.pending_uploads.pop(chat_id, None)
            doc_url = self._document_url(doc_id)
            await query.edit_message_text(
                f"Metadata saved.\n\n[Open in Paperless]({doc_url})",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def _handle_tag_toggle(self, update, context, chat_id: int, data: str):
        """Handle tag checkbox toggle."""
        query = update.callback_query
        parts = data.split(":")
        current_state = parts[1]  # "x" (checked) or "o" (unchecked)
        tag_id = int(parts[2])
        doc_id = int(parts[3])

        pending = self.pending_uploads.get(chat_id)
        if not pending:
            return

        selected = pending.get("selected_tags", set())
        if current_state == "o":
            selected.add(tag_id)
        else:
            selected.discard(tag_id)
        pending["selected_tags"] = selected

        tags = sorted(self.client._tags_cache.items(), key=lambda x: x[1])
        # Figure out current page from tag position
        tag_ids = [t[0] for t in tags]
        try:
            idx = tag_ids.index(tag_id)
            page = idx // 8
        except ValueError:
            page = 0

        await query.edit_message_reply_markup(
            reply_markup=build_tag_selection_keyboard(tags, selected, doc_id, page=page),
        )

    async def _handle_tag_page(self, update, context, chat_id: int, data: str):
        """Handle tag pagination."""
        query = update.callback_query
        parts = data.split(":")
        page = int(parts[1])
        doc_id = int(parts[2])

        pending = self.pending_uploads.get(chat_id)
        selected = pending.get("selected_tags", set()) if pending else set()
        tags = sorted(self.client._tags_cache.items(), key=lambda x: x[1])

        await query.edit_message_reply_markup(
            reply_markup=build_tag_selection_keyboard(tags, selected, doc_id, page=page),
        )

    async def _handle_tag_confirm(self, update, context, chat_id: int, data: str):
        """Handle tag confirmation \u2014 apply selected tags to document."""
        query = update.callback_query
        doc_id = int(data.split(":")[1])

        pending = self.pending_uploads.get(chat_id)
        selected = pending.get("selected_tags", set()) if pending else set()

        if selected:
            try:
                await self.client.update_document(doc_id, tags=list(selected))
                tag_names = [self.client._tags_cache.get(tid, f"#{tid}") for tid in selected]
                await query.edit_message_text(
                    f"Tags set: {', '.join(tag_names)}\n\nContinue setting metadata?",
                    reply_markup=build_metadata_keyboard(doc_id),
                )
            except Exception:
                logger.exception("Failed to update tags")
                await query.edit_message_text("Failed to update tags.", reply_markup=build_metadata_keyboard(doc_id))
        else:
            await query.edit_message_text(
                "No tags selected.\n\nContinue setting metadata?",
                reply_markup=build_metadata_keyboard(doc_id),
            )

    async def _handle_single_select(self, update, context, chat_id: int, data: str, field_name: str):
        """Handle single-select (correspondent or document type)."""
        query = update.callback_query
        parts = data.split(":")
        value = parts[1]
        doc_id = int(parts[2])

        if value == "skip":
            await query.edit_message_text(
                f"{field_name.replace('_', ' ').title()} skipped.\n\nContinue setting metadata?",
                reply_markup=build_metadata_keyboard(doc_id),
            )
            return

        try:
            item_id = int(value)
            await self.client.update_document(doc_id, **{field_name: item_id})

            # Get name from cache
            if field_name == "correspondent":
                name = self.client._correspondents_cache.get(item_id, f"#{item_id}")
            else:
                name = self.client._doc_types_cache.get(item_id, f"#{item_id}")

            await query.edit_message_text(
                f"{field_name.replace('_', ' ').title()} set: {name}\n\nContinue setting metadata?",
                reply_markup=build_metadata_keyboard(doc_id),
            )
        except Exception:
            logger.exception(f"Failed to update {field_name}")
            await query.edit_message_text(
                f"Failed to update {field_name}.",
                reply_markup=build_metadata_keyboard(doc_id),
            )

    async def _handle_select_page(self, update, context, chat_id: int, data: str, prefix: str):
        """Handle pagination for correspondent/document type selection."""
        query = update.callback_query
        parts = data.split(":")
        page = int(parts[1])
        doc_id = int(parts[2])

        if prefix == "corr":
            items = sorted(self.client._correspondents_cache.items(), key=lambda x: x[1])
        else:
            items = sorted(self.client._doc_types_cache.items(), key=lambda x: x[1])

        await query.edit_message_reply_markup(
            reply_markup=build_single_select_keyboard(items, prefix, doc_id, page=page),
        )

    # --- Download ---

    async def _handle_download(self, update, context, chat_id: int, doc_id: int):
        """Download a document and send it to the user."""
        try:
            file_bytes, filename = await self.client.download_document(doc_id)

            if len(file_bytes) > TELEGRAM_FILE_LIMIT:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"File too large for Telegram ({len(file_bytes) / 1024 / 1024:.1f}MB > 50MB limit).",
                )
                return

            await context.bot.send_document(
                chat_id=chat_id,
                document=file_bytes,
                filename=filename,
            )
        except Exception:
            logger.exception(f"Download failed for document {doc_id}")
            await context.bot.send_message(chat_id=chat_id, text="Download failed.")

    # --- Search pagination ---

    async def _handle_search_page(self, update, context, chat_id: int, page: int):
        """Handle search results pagination."""
        query = update.callback_query
        search_query = self.search_queries.get(chat_id)
        if not search_query:
            await query.edit_message_text("Search expired. Send a new query.")
            return

        try:
            documents, total = await self.client.search_documents(
                search_query, page=page, page_size=self.config.max_search_results
            )
            text = f"*Search: {search_query}* ({total} results)\n\n"
            text += self._format_document_list(documents)
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_search_results_keyboard(documents, page, total, self.config.max_search_results),
            )
        except Exception:
            logger.exception("Search pagination failed")
            await query.edit_message_text("Search failed.")

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _format_document_list(documents: list) -> str:
        """Format a list of documents for display."""
        lines = []
        for doc in documents:
            line = f"*{doc.title}*"
            details = []
            if doc.correspondent:
                details.append(f"Corr: {doc.correspondent}")
            if doc.document_type:
                details.append(f"Type: {doc.document_type}")
            if doc.tags:
                details.append(f"Tags: {', '.join(doc.tags)}")
            if details:
                line += f"\n  {' | '.join(details)}"
            line += f"\n  Added: {doc.added}"
            if doc.content:
                snippet = doc.content.replace("*", "").replace("_", "").replace("`", "")[:100]
                line += f'\n  "{snippet}..."'
            lines.append(line)
        return "\n\n".join(lines)


async def _post_init(application: Application) -> None:
    """Register bot commands with Telegram after initialization."""
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


def create_bot(config: Config) -> Application:
    """Create and configure the Telegram bot application."""
    bot = PaperlessBot(config)

    app = Application.builder().token(config.telegram_bot_token).post_init(_post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start", bot.cmd_start))
    app.add_handler(CommandHandler("help", bot.cmd_help))
    app.add_handler(CommandHandler("search", bot.cmd_search))
    app.add_handler(CommandHandler("recent", bot.cmd_recent))
    app.add_handler(CommandHandler("inbox", bot.cmd_inbox))
    app.add_handler(CommandHandler("stats", bot.cmd_stats))

    # Callback query handler (inline keyboard buttons)
    app.add_handler(CallbackQueryHandler(bot.handle_callback))

    # Document/photo handlers \u2014 must come before text handler
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))

    # Text message handler (search or new metadata name) \u2014 must be last
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    logger.info("Telegram bot configured")
    return app
