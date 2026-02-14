"""
Inline keyboard builders for the Telegram bot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from paperless_bot.api.client import Document


def build_metadata_keyboard(doc_id: int) -> InlineKeyboardMarkup:
    """Build post-upload metadata assignment keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Set Tags", callback_data=f"meta:tags:{doc_id}"),
                InlineKeyboardButton("Set Correspondent", callback_data=f"meta:corr:{doc_id}"),
            ],
            [
                InlineKeyboardButton("Set Document Type", callback_data=f"meta:dtype:{doc_id}"),
                InlineKeyboardButton("Done", callback_data=f"meta:done:{doc_id}"),
            ],
        ]
    )


def build_tag_selection_keyboard(
    tags: list[tuple[int, str]],
    selected_ids: set[int],
    doc_id: int,
    page: int = 0,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Build paginated tag selection keyboard with toggle checkmarks."""
    start = page * page_size
    end = min(start + page_size, len(tags))
    page_tags = tags[start:end]

    buttons = []
    for tag_id, tag_name in page_tags:
        checked = tag_id in selected_ids
        prefix = "x" if checked else "o"
        icon = "[x]" if checked else "[ ]"
        label = f"{icon} {tag_name}"
        if len(label) > 60:
            label = label[:57] + "..."
        buttons.append([InlineKeyboardButton(label, callback_data=f"tag:{prefix}:{tag_id}:{doc_id}")])

    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("< Prev", callback_data=f"tagp:{page - 1}:{doc_id}"))
    if end < len(tags):
        nav_row.append(InlineKeyboardButton("Next >", callback_data=f"tagp:{page + 1}:{doc_id}"))
    if nav_row:
        buttons.append(nav_row)

    # Action row: + New and Confirm
    buttons.append(
        [
            InlineKeyboardButton("+ New Tag", callback_data=f"newtag:{doc_id}"),
            InlineKeyboardButton("Confirm Tags", callback_data=f"tagok:{doc_id}"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def build_single_select_keyboard(
    items: list[tuple[int, str]],
    callback_prefix: str,
    doc_id: int,
    page: int = 0,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Build paginated single-select keyboard for correspondents or document types."""
    start = page * page_size
    end = min(start + page_size, len(items))

    buttons = []
    for item_id, item_name in items[start:end]:
        label = item_name
        if len(label) > 60:
            label = label[:57] + "..."
        buttons.append([InlineKeyboardButton(label, callback_data=f"{callback_prefix}:{item_id}:{doc_id}")])

    nav_row = []
    page_prefix = f"{callback_prefix}p"
    if page > 0:
        nav_row.append(InlineKeyboardButton("< Prev", callback_data=f"{page_prefix}:{page - 1}:{doc_id}"))
    if end < len(items):
        nav_row.append(InlineKeyboardButton("Next >", callback_data=f"{page_prefix}:{page + 1}:{doc_id}"))
    if nav_row:
        buttons.append(nav_row)

    # Determine the "+ New" callback prefix
    new_prefix = f"new{callback_prefix}"  # newcorr or newdtype
    new_label = "+ New Correspondent" if callback_prefix == "corr" else "+ New Type"
    buttons.append(
        [
            InlineKeyboardButton(new_label, callback_data=f"{new_prefix}:{doc_id}"),
            InlineKeyboardButton("Skip", callback_data=f"{callback_prefix}:skip:{doc_id}"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def build_search_results_keyboard(
    documents: list[Document],
    page: int,
    total: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    """Build search results keyboard with download and pagination."""
    buttons = []
    for doc in documents:
        label = f"Download: {doc.title[:40]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl:{doc.id}")])

    # Pagination
    total_pages = (total + page_size - 1) // page_size
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("< Prev", callback_data=f"sp:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next >", callback_data=f"sp:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(buttons)


def build_document_list_keyboard(documents: list[Document]) -> InlineKeyboardMarkup:
    """Build keyboard for a document list (recent, inbox)."""
    buttons = []
    for doc in documents:
        label = f"Download: {doc.title[:40]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl:{doc.id}")])
    return InlineKeyboardMarkup(buttons)
