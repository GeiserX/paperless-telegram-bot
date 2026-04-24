"""Tests for inline keyboard builders."""


from paperless_bot.api.client import Document
from paperless_bot.bot.keyboards import (
    build_document_list_keyboard,
    build_metadata_keyboard,
    build_search_results_keyboard,
    build_single_select_keyboard,
    build_tag_selection_keyboard,
)


def _make_doc(doc_id=1, title="Test Doc"):
    return Document(
        id=doc_id,
        title=title,
        correspondent=None,
        document_type=None,
        tags=[],
        created="2025-01-01",
        added="2025-01-01",
    )


# ---------------------------------------------------------------------------
# build_metadata_keyboard
# ---------------------------------------------------------------------------

class TestMetadataKeyboard:
    def test_has_four_buttons(self):
        kb = build_metadata_keyboard(42)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 4

    def test_callback_data_contains_doc_id(self):
        kb = build_metadata_keyboard(99)
        all_data = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert all("99" in d for d in all_data)

    def test_button_labels(self):
        kb = build_metadata_keyboard(1)
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Set Tags" in labels
        assert "Set Correspondent" in labels
        assert "Set Document Type" in labels
        assert "Done" in labels


# ---------------------------------------------------------------------------
# build_tag_selection_keyboard
# ---------------------------------------------------------------------------

class TestTagSelectionKeyboard:
    def test_basic_tags(self):
        tags = [(1, "alpha"), (2, "beta"), (3, "gamma")]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42)
        # 3 tag rows + 1 action row (+ New Tag, Confirm)
        assert len(kb.inline_keyboard) == 4

    def test_selected_tags_show_checkmark(self):
        tags = [(1, "alpha"), (2, "beta")]
        kb = build_tag_selection_keyboard(tags, {1}, doc_id=42)
        first_btn = kb.inline_keyboard[0][0]
        assert "[x]" in first_btn.text
        second_btn = kb.inline_keyboard[1][0]
        assert "[ ]" in second_btn.text

    def test_callback_data_format(self):
        tags = [(1, "alpha")]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42)
        data = kb.inline_keyboard[0][0].callback_data
        assert data == "tag:o:1:42"

    def test_checked_callback_data(self):
        tags = [(1, "alpha")]
        kb = build_tag_selection_keyboard(tags, {1}, doc_id=42)
        data = kb.inline_keyboard[0][0].callback_data
        assert data == "tag:x:1:42"

    def test_pagination_not_shown_when_few_tags(self):
        tags = [(i, f"tag{i}") for i in range(5)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42)
        # 5 tag rows + 1 action row (no nav row)
        assert len(kb.inline_keyboard) == 6

    def test_pagination_shown_when_many_tags(self):
        tags = [(i, f"tag{i}") for i in range(20)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42, page=0)
        # 8 tag rows + 1 nav row + 1 action row
        assert len(kb.inline_keyboard) == 10

    def test_page_1_has_prev_and_next(self):
        tags = [(i, f"tag{i}") for i in range(25)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42, page=1)
        # Find nav row (second to last)
        nav_row = kb.inline_keyboard[-2]
        nav_labels = [btn.text for btn in nav_row]
        assert "< Prev" in nav_labels
        assert "Next >" in nav_labels

    def test_first_page_no_prev(self):
        tags = [(i, f"tag{i}") for i in range(20)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42, page=0)
        nav_row = kb.inline_keyboard[-2]
        nav_labels = [btn.text for btn in nav_row]
        assert "< Prev" not in nav_labels
        assert "Next >" in nav_labels

    def test_last_page_no_next(self):
        tags = [(i, f"tag{i}") for i in range(10)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42, page=1)
        # Page 1 has only 2 tags (indices 8-9)
        # No nav row needed since we're at the end and there's only 2 pages
        action_row = kb.inline_keyboard[-1]
        assert any("Confirm" in btn.text for btn in action_row)

    def test_action_row_has_new_and_confirm(self):
        tags = [(1, "alpha")]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42)
        action_row = kb.inline_keyboard[-1]
        labels = [btn.text for btn in action_row]
        assert "+ New Tag" in labels
        assert "Confirm Tags" in labels

    def test_long_tag_name_truncated(self):
        tags = [(1, "a" * 100)]
        kb = build_tag_selection_keyboard(tags, set(), doc_id=42)
        label = kb.inline_keyboard[0][0].text
        assert len(label) <= 60
        assert label.endswith("...")


# ---------------------------------------------------------------------------
# build_single_select_keyboard
# ---------------------------------------------------------------------------

class TestSingleSelectKeyboard:
    def test_basic_items(self):
        items = [(1, "ACME"), (2, "Corp")]
        kb = build_single_select_keyboard(items, "corr", doc_id=42)
        # 2 item rows + 1 action row
        assert len(kb.inline_keyboard) == 3

    def test_callback_data_format(self):
        items = [(5, "ACME")]
        kb = build_single_select_keyboard(items, "corr", doc_id=42)
        data = kb.inline_keyboard[0][0].callback_data
        assert data == "corr:5:42"

    def test_skip_button(self):
        items = [(1, "ACME")]
        kb = build_single_select_keyboard(items, "corr", doc_id=42)
        action_row = kb.inline_keyboard[-1]
        skip_btn = [btn for btn in action_row if btn.text == "Skip"][0]
        assert skip_btn.callback_data == "corr:skip:42"

    def test_new_correspondent_button(self):
        items = [(1, "ACME")]
        kb = build_single_select_keyboard(items, "corr", doc_id=42)
        action_row = kb.inline_keyboard[-1]
        new_btn = [btn for btn in action_row if "New" in btn.text][0]
        assert new_btn.text == "+ New Correspondent"
        assert new_btn.callback_data == "newcorr:42"

    def test_new_type_button(self):
        items = [(1, "Bill")]
        kb = build_single_select_keyboard(items, "dtype", doc_id=42)
        action_row = kb.inline_keyboard[-1]
        new_btn = [btn for btn in action_row if "New" in btn.text][0]
        assert new_btn.text == "+ New Type"
        assert new_btn.callback_data == "newdtype:42"

    def test_pagination(self):
        items = [(i, f"item{i}") for i in range(20)]
        kb = build_single_select_keyboard(items, "corr", doc_id=42, page=0)
        # 8 items + 1 nav row + 1 action row
        assert len(kb.inline_keyboard) == 10

    def test_pagination_data(self):
        items = [(i, f"item{i}") for i in range(20)]
        kb = build_single_select_keyboard(items, "corr", doc_id=42, page=0)
        nav_row = kb.inline_keyboard[-2]
        next_btn = [btn for btn in nav_row if "Next" in btn.text][0]
        assert next_btn.callback_data == "corrp:1:42"

    def test_long_name_truncated(self):
        items = [(1, "a" * 100)]
        kb = build_single_select_keyboard(items, "corr", doc_id=42)
        label = kb.inline_keyboard[0][0].text
        assert len(label) <= 60
        assert label.endswith("...")


# ---------------------------------------------------------------------------
# build_search_results_keyboard
# ---------------------------------------------------------------------------

class TestSearchResultsKeyboard:
    def test_basic(self):
        docs = [_make_doc(1, "Invoice"), _make_doc(2, "Receipt")]
        kb = build_search_results_keyboard(docs, page=1, total=2, page_size=10)
        assert len(kb.inline_keyboard) == 2  # 2 download buttons, no nav

    def test_download_callback_data(self):
        docs = [_make_doc(42, "Invoice")]
        kb = build_search_results_keyboard(docs, page=1, total=1, page_size=10)
        assert kb.inline_keyboard[0][0].callback_data == "dl:42"

    def test_download_label_truncated(self):
        docs = [_make_doc(1, "A" * 60)]
        kb = build_search_results_keyboard(docs, page=1, total=1, page_size=10)
        label = kb.inline_keyboard[0][0].text
        assert label.startswith("Download: ")

    def test_pagination_next(self):
        docs = [_make_doc()]
        kb = build_search_results_keyboard(docs, page=1, total=20, page_size=10)
        nav_row = kb.inline_keyboard[-1]
        labels = [btn.text for btn in nav_row]
        assert "Next >" in labels

    def test_pagination_prev(self):
        docs = [_make_doc()]
        kb = build_search_results_keyboard(docs, page=2, total=20, page_size=10)
        nav_row = kb.inline_keyboard[-1]
        labels = [btn.text for btn in nav_row]
        assert "< Prev" in labels

    def test_pagination_both(self):
        docs = [_make_doc()]
        kb = build_search_results_keyboard(docs, page=2, total=30, page_size=10)
        nav_row = kb.inline_keyboard[-1]
        labels = [btn.text for btn in nav_row]
        assert "< Prev" in labels
        assert "Next >" in labels

    def test_no_pagination_single_page(self):
        docs = [_make_doc()]
        kb = build_search_results_keyboard(docs, page=1, total=5, page_size=10)
        # Only download buttons, no nav
        assert len(kb.inline_keyboard) == 1

    def test_page_callback_data(self):
        docs = [_make_doc()]
        kb = build_search_results_keyboard(docs, page=1, total=20, page_size=10)
        nav_row = kb.inline_keyboard[-1]
        next_btn = [btn for btn in nav_row if "Next" in btn.text][0]
        assert next_btn.callback_data == "sp:2"


# ---------------------------------------------------------------------------
# build_document_list_keyboard
# ---------------------------------------------------------------------------

class TestDocumentListKeyboard:
    def test_basic(self):
        docs = [_make_doc(1, "Invoice"), _make_doc(2, "Receipt")]
        kb = build_document_list_keyboard(docs)
        assert len(kb.inline_keyboard) == 2
        assert len(kb.inline_keyboard[0]) == 1  # Just download

    def test_inbox_mode(self):
        docs = [_make_doc(1, "Invoice")]
        kb = build_document_list_keyboard(docs, inbox_mode=True)
        row = kb.inline_keyboard[0]
        assert len(row) == 2  # Download + Reviewed
        assert row[1].text == "Reviewed"
        assert row[1].callback_data == "rev:1"

    def test_download_data(self):
        docs = [_make_doc(42, "Invoice")]
        kb = build_document_list_keyboard(docs)
        assert kb.inline_keyboard[0][0].callback_data == "dl:42"

    def test_inbox_title_truncated_shorter(self):
        docs = [_make_doc(1, "A" * 60)]
        kb_normal = build_document_list_keyboard(docs)
        kb_inbox = build_document_list_keyboard(docs, inbox_mode=True)
        # Inbox mode truncates to 30 chars, normal to 40
        assert len(kb_inbox.inline_keyboard[0][0].text) < len(kb_normal.inline_keyboard[0][0].text)
