"""Tests for Paperless-NGX API client."""

import pytest
import respx
from httpx import Response

from paperless_bot.api.client import (
    Correspondent,
    Document,
    DocumentType,
    PaperlessClient,
    Tag,
    TaskResult,
)


@pytest.fixture
def client():
    return PaperlessClient("http://localhost:8000", "test-token")


@pytest.fixture(autouse=True)
def _mock_api():
    with respx.mock:
        yield


def _mock_cache_endpoints(tags=None, correspondents=None, doc_types=None, inbox_tag=False):
    """Set up mock responses for cache refresh endpoints."""
    if tags is None:
        tags = [
            {"id": 1, "name": "invoice", "is_inbox_tag": False},
            {"id": 2, "name": "Inbox", "is_inbox_tag": inbox_tag},
        ]
    respx.get("http://localhost:8000/api/tags/").mock(return_value=Response(200, json={"results": tags, "next": None}))
    if correspondents is None:
        correspondents = [{"id": 1, "name": "ACME"}]
    respx.get("http://localhost:8000/api/correspondents/").mock(
        return_value=Response(200, json={"results": correspondents, "next": None})
    )
    if doc_types is None:
        doc_types = [{"id": 1, "name": "Bill"}]
    respx.get("http://localhost:8000/api/document_types/").mock(
        return_value=Response(200, json={"results": doc_types, "next": None})
    )


def _make_doc_response(
    doc_id=42,
    title="Test Invoice",
    correspondent=1,
    document_type=1,
    tags=None,
    content="This is a test invoice content",
):
    return {
        "id": doc_id,
        "title": title,
        "correspondent": correspondent,
        "document_type": document_type,
        "tags": tags or [1],
        "created": "2025-01-15T00:00:00Z",
        "added": "2025-01-15T12:00:00Z",
        "content": content,
    }


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_document(self):
        doc = Document(
            id=1,
            title="Test",
            correspondent="ACME",
            document_type="Bill",
            tags=["invoice"],
            created="2025-01-01",
            added="2025-01-01",
        )
        assert doc.id == 1
        assert doc.content is None

    def test_document_with_content(self):
        doc = Document(
            id=1,
            title="Test",
            correspondent=None,
            document_type=None,
            tags=[],
            created="",
            added="",
            content="Some text",
        )
        assert doc.content == "Some text"

    def test_task_result_defaults(self):
        result = TaskResult(status="success")
        assert result.doc_id is None
        assert result.message is None

    def test_tag(self):
        tag = Tag(id=1, name="invoice")
        assert tag.id == 1

    def test_correspondent(self):
        corr = Correspondent(id=1, name="ACME")
        assert corr.name == "ACME"

    def test_document_type(self):
        dt = DocumentType(id=1, name="Bill")
        assert dt.name == "Bill"


# ---------------------------------------------------------------------------
# Client init and close
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_strips_trailing_slash(self):
        c = PaperlessClient("http://localhost:8000/", "token")
        assert c.base_url == "http://localhost:8000"

    def test_no_trailing_slash(self):
        c = PaperlessClient("http://localhost:8000", "token")
        assert c.base_url == "http://localhost:8000"

    def test_inbox_tag_override(self):
        c = PaperlessClient("http://localhost:8000", "token", inbox_tag_name="custom")
        assert c._inbox_tag_name_override == "custom"

    async def test_close(self, client):
        # Should not raise
        await client.close()


# ---------------------------------------------------------------------------
# Cache refresh
# ---------------------------------------------------------------------------


class TestCacheRefresh:
    @respx.mock
    async def test_refresh_cache_populates(self, client):
        _mock_cache_endpoints()
        await client.refresh_cache()
        assert 1 in client._tags_cache
        assert client._tags_cache[1] == "invoice"
        assert 1 in client._correspondents_cache
        assert 1 in client._doc_types_cache

    @respx.mock
    async def test_inbox_tag_autodetect(self, client):
        _mock_cache_endpoints(inbox_tag=True)
        await client.refresh_cache()
        assert client._inbox_tag_id == 2

    @respx.mock
    async def test_inbox_tag_not_detected_without_flag(self, client):
        _mock_cache_endpoints(inbox_tag=False)
        await client.refresh_cache()
        assert client._inbox_tag_id is None

    @respx.mock
    async def test_inbox_tag_name_override(self):
        c = PaperlessClient("http://localhost:8000", "test-token", inbox_tag_name="invoice")
        tags = [
            {"id": 1, "name": "invoice", "is_inbox_tag": False},
            {"id": 2, "name": "Inbox", "is_inbox_tag": True},
        ]
        respx.get("http://localhost:8000/api/tags/").mock(
            return_value=Response(200, json={"results": tags, "next": None})
        )
        respx.get("http://localhost:8000/api/correspondents/").mock(
            return_value=Response(200, json={"results": [], "next": None})
        )
        respx.get("http://localhost:8000/api/document_types/").mock(
            return_value=Response(200, json={"results": [], "next": None})
        )
        await c.refresh_cache()
        assert c._inbox_tag_id == 1  # Found by name, not is_inbox_tag

    @respx.mock
    async def test_inbox_tag_name_override_not_found(self):
        c = PaperlessClient("http://localhost:8000", "test-token", inbox_tag_name="nonexistent")
        tags = [{"id": 1, "name": "invoice", "is_inbox_tag": False}]
        respx.get("http://localhost:8000/api/tags/").mock(
            return_value=Response(200, json={"results": tags, "next": None})
        )
        respx.get("http://localhost:8000/api/correspondents/").mock(
            return_value=Response(200, json={"results": [], "next": None})
        )
        respx.get("http://localhost:8000/api/document_types/").mock(
            return_value=Response(200, json={"results": [], "next": None})
        )
        await c.refresh_cache()
        assert c._inbox_tag_id is None

    @respx.mock
    async def test_ensure_cache_populates_if_empty(self, client):
        _mock_cache_endpoints()
        assert not client._tags_cache
        await client._ensure_cache()
        assert client._tags_cache  # Now populated

    @respx.mock
    async def test_ensure_cache_skips_if_populated(self, client):
        client._tags_cache = {1: "already"}
        # No mock needed because it should NOT make requests
        await client._ensure_cache()
        assert client._tags_cache == {1: "already"}


# ---------------------------------------------------------------------------
# Search documents
# ---------------------------------------------------------------------------


class TestSearchDocuments:
    @respx.mock
    async def test_basic_search(self, client):
        _mock_cache_endpoints()
        respx.get("http://localhost:8000/api/documents/").mock(
            return_value=Response(
                200,
                json={"count": 1, "results": [_make_doc_response()]},
            )
        )
        documents, total = await client.search_documents("invoice")
        assert total == 1
        assert len(documents) == 1
        assert documents[0].title == "Test Invoice"
        assert documents[0].correspondent == "ACME"
        assert documents[0].document_type == "Bill"
        assert documents[0].tags == ["invoice"]

    @respx.mock
    async def test_search_pagination(self, client):
        _mock_cache_endpoints()
        respx.get("http://localhost:8000/api/documents/").mock(
            return_value=Response(
                200,
                json={"count": 50, "results": [_make_doc_response()]},
            )
        )
        documents, total = await client.search_documents("test", page=2, page_size=5)
        assert total == 50


# ---------------------------------------------------------------------------
# Recent documents
# ---------------------------------------------------------------------------


class TestRecentDocuments:
    @respx.mock
    async def test_get_recent(self, client):
        _mock_cache_endpoints()
        respx.get("http://localhost:8000/api/documents/").mock(
            return_value=Response(
                200,
                json={"results": [_make_doc_response()]},
            )
        )
        docs = await client.get_recent_documents(10)
        assert len(docs) == 1


# ---------------------------------------------------------------------------
# Get document
# ---------------------------------------------------------------------------


class TestGetDocument:
    @respx.mock
    async def test_get_document(self, client):
        _mock_cache_endpoints()
        respx.get("http://localhost:8000/api/documents/42/").mock(return_value=Response(200, json=_make_doc_response()))
        doc = await client.get_document(42)
        assert doc.id == 42
        assert doc.title == "Test Invoice"


# ---------------------------------------------------------------------------
# Upload document
# ---------------------------------------------------------------------------


class TestUploadDocument:
    @respx.mock
    async def test_upload_basic(self, client):
        respx.post("http://localhost:8000/api/documents/post_document/").mock(
            return_value=Response(200, text='"abc-123-task-id"')
        )
        task_id = await client.upload_document(b"file content", "test.pdf")
        assert task_id == "abc-123-task-id"

    @respx.mock
    async def test_upload_with_metadata(self, client):
        route = respx.post("http://localhost:8000/api/documents/post_document/").mock(
            return_value=Response(200, text='"task-456"')
        )
        task_id = await client.upload_document(
            b"data", "test.pdf", title="My Doc", correspondent=1, document_type=2, tags=[3, 4]
        )
        assert task_id == "task-456"

    @respx.mock
    async def test_upload_strips_quotes(self, client):
        respx.post("http://localhost:8000/api/documents/post_document/").mock(
            return_value=Response(200, text='  "task-id-padded"  ')
        )
        task_id = await client.upload_document(b"data", "test.pdf")
        assert task_id == "task-id-padded"


# ---------------------------------------------------------------------------
# Wait for task
# ---------------------------------------------------------------------------


class TestWaitForTask:
    @respx.mock
    async def test_task_success(self, client):
        call_count = 0

        def task_side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return Response(200, json=[{"status": "PENDING", "result": None}])
            return Response(200, json=[{"status": "SUCCESS", "related_document": 42, "result": None}])

        respx.get("http://localhost:8000/api/tasks/").mock(side_effect=task_side_effect)

        result = await client.wait_for_task("task-abc", timeout=10)
        assert result.status == "success"
        assert result.doc_id == 42

    @respx.mock
    async def test_task_failure(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(200, json=[{"status": "FAILURE", "result": "OCR failed"}])
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "failed"
        assert "OCR failed" in result.message

    @respx.mock
    async def test_task_duplicate(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "status": "FAILURE",
                        "result": "Not consuming: It is a duplicate of Invoice (#42).",
                    }
                ],
            )
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "duplicate"
        assert result.doc_id == 42

    @respx.mock
    async def test_task_duplicate_no_id(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "status": "FAILURE",
                        "result": "Not consuming: It is a duplicate (no ID).",
                    }
                ],
            )
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "duplicate"
        assert result.doc_id is None

    @respx.mock
    async def test_task_revoked(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(200, json=[{"status": "REVOKED", "result": "cancelled"}])
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "failed"

    @respx.mock
    async def test_task_timeout(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(200, json=[{"status": "PENDING", "result": None}])
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "timeout"

    @respx.mock
    async def test_task_empty_response(self, client):
        respx.get("http://localhost:8000/api/tasks/").mock(return_value=Response(200, json=[]))
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "timeout"

    @respx.mock
    async def test_task_dict_response(self, client):
        """Tasks endpoint sometimes returns a dict instead of a list."""
        respx.get("http://localhost:8000/api/tasks/").mock(
            return_value=Response(200, json={"status": "SUCCESS", "related_document": 7, "result": None})
        )
        result = await client.wait_for_task("task-abc", timeout=4)
        assert result.status == "success"
        assert result.doc_id == 7

    @respx.mock
    async def test_task_polling_error_recovery(self, client):
        """Errors during polling should not abort, just continue."""
        call_count = 0

        def task_side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return Response(200, json=[{"status": "SUCCESS", "related_document": 42, "result": None}])

        respx.get("http://localhost:8000/api/tasks/").mock(side_effect=task_side_effect)

        result = await client.wait_for_task("task-abc", timeout=10)
        assert result.status == "success"
        assert result.doc_id == 42


# ---------------------------------------------------------------------------
# _extract_duplicate_id
# ---------------------------------------------------------------------------


class TestExtractDuplicateId:
    def test_standard_message(self):
        msg = "Not consuming file.pdf: It is a duplicate of Invoice April (#42)."
        assert PaperlessClient._extract_duplicate_id(msg) == 42

    def test_no_id(self):
        msg = "Not consuming: something went wrong"
        assert PaperlessClient._extract_duplicate_id(msg) is None

    def test_multiple_ids_takes_first(self):
        msg = "duplicate of Invoice (#42) and Receipt (#99)"
        assert PaperlessClient._extract_duplicate_id(msg) == 42


# ---------------------------------------------------------------------------
# Download document
# ---------------------------------------------------------------------------


class TestDownloadDocument:
    @respx.mock
    async def test_download_with_filename(self, client):
        respx.get("http://localhost:8000/api/documents/42/download/").mock(
            return_value=Response(
                200,
                content=b"pdf content",
                headers={"content-disposition": 'attachment; filename="invoice.pdf"'},
            )
        )
        file_bytes, filename = await client.download_document(42)
        assert file_bytes == b"pdf content"
        assert filename == "invoice.pdf"

    @respx.mock
    async def test_download_no_filename(self, client):
        respx.get("http://localhost:8000/api/documents/42/download/").mock(
            return_value=Response(200, content=b"pdf content")
        )
        file_bytes, filename = await client.download_document(42)
        assert file_bytes == b"pdf content"
        assert filename == "document_42.pdf"

    @respx.mock
    async def test_download_empty_content_disposition(self, client):
        respx.get("http://localhost:8000/api/documents/42/download/").mock(
            return_value=Response(
                200,
                content=b"pdf content",
                headers={"content-disposition": "attachment"},
            )
        )
        _, filename = await client.download_document(42)
        assert filename == "document_42.pdf"


# ---------------------------------------------------------------------------
# Update document
# ---------------------------------------------------------------------------


class TestUpdateDocument:
    @respx.mock
    async def test_update(self, client):
        _mock_cache_endpoints()
        respx.patch("http://localhost:8000/api/documents/42/").mock(
            return_value=Response(200, json=_make_doc_response(tags=[1, 2]))
        )
        doc = await client.update_document(42, tags=[1, 2])
        assert doc.id == 42


# ---------------------------------------------------------------------------
# Inbox documents
# ---------------------------------------------------------------------------


class TestInboxDocuments:
    @respx.mock
    async def test_get_inbox_with_tag(self, client):
        _mock_cache_endpoints(inbox_tag=True)
        await client.refresh_cache()
        respx.get("http://localhost:8000/api/documents/").mock(
            return_value=Response(
                200,
                json={"count": 1, "results": [_make_doc_response()]},
            )
        )
        docs, total = await client.get_inbox_documents(10)
        assert total == 1
        assert len(docs) == 1

    @respx.mock
    async def test_get_inbox_no_tag(self, client):
        _mock_cache_endpoints(inbox_tag=False)
        await client.refresh_cache()
        docs, total = await client.get_inbox_documents(10)
        assert total == 0
        assert docs == []

    @respx.mock
    async def test_remove_inbox_tag(self, client):
        _mock_cache_endpoints(inbox_tag=True)
        await client.refresh_cache()
        respx.get("http://localhost:8000/api/documents/42/").mock(return_value=Response(200, json={"tags": [1, 2]}))
        respx.patch("http://localhost:8000/api/documents/42/").mock(return_value=Response(200, json={}))
        await client.remove_inbox_tag(42)

    @respx.mock
    async def test_remove_inbox_tag_not_present(self, client):
        _mock_cache_endpoints(inbox_tag=True)
        await client.refresh_cache()
        respx.get("http://localhost:8000/api/documents/42/").mock(
            return_value=Response(200, json={"tags": [1]})  # tag 2 not present
        )
        # Should not call patch
        await client.remove_inbox_tag(42)

    @respx.mock
    async def test_remove_inbox_tag_no_inbox(self, client):
        _mock_cache_endpoints(inbox_tag=False)
        await client.refresh_cache()
        # No inbox tag ID means nothing should happen
        await client.remove_inbox_tag(42)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestTags:
    @respx.mock
    async def test_get_tags(self, client):
        respx.get("http://localhost:8000/api/tags/").mock(
            return_value=Response(
                200,
                json={"results": [{"id": 1, "name": "invoice"}, {"id": 2, "name": "receipt"}], "next": None},
            )
        )
        tags = await client.get_tags()
        assert len(tags) == 2
        assert tags[0].name == "invoice"

    @respx.mock
    async def test_create_tag(self, client):
        respx.post("http://localhost:8000/api/tags/").mock(return_value=Response(200, json={"id": 5, "name": "newtag"}))
        tag = await client.create_tag("newtag")
        assert tag.id == 5
        assert tag.name == "newtag"
        assert client._tags_cache[5] == "newtag"


# ---------------------------------------------------------------------------
# Correspondents
# ---------------------------------------------------------------------------


class TestCorrespondents:
    @respx.mock
    async def test_get_correspondents(self, client):
        respx.get("http://localhost:8000/api/correspondents/").mock(
            return_value=Response(
                200,
                json={"results": [{"id": 1, "name": "ACME"}], "next": None},
            )
        )
        corrs = await client.get_correspondents()
        assert len(corrs) == 1
        assert corrs[0].name == "ACME"

    @respx.mock
    async def test_create_correspondent(self, client):
        respx.post("http://localhost:8000/api/correspondents/").mock(
            return_value=Response(200, json={"id": 3, "name": "NewCorp"})
        )
        corr = await client.create_correspondent("NewCorp")
        assert corr.id == 3
        assert client._correspondents_cache[3] == "NewCorp"


# ---------------------------------------------------------------------------
# Document types
# ---------------------------------------------------------------------------


class TestDocumentTypes:
    @respx.mock
    async def test_get_document_types(self, client):
        respx.get("http://localhost:8000/api/document_types/").mock(
            return_value=Response(
                200,
                json={"results": [{"id": 1, "name": "Bill"}], "next": None},
            )
        )
        types = await client.get_document_types()
        assert len(types) == 1
        assert types[0].name == "Bill"

    @respx.mock
    async def test_create_document_type(self, client):
        respx.post("http://localhost:8000/api/document_types/").mock(
            return_value=Response(200, json={"id": 7, "name": "Contract"})
        )
        dt = await client.create_document_type("Contract")
        assert dt.id == 7
        assert client._doc_types_cache[7] == "Contract"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestStatistics:
    @respx.mock
    async def test_get_statistics(self, client):
        respx.get("http://localhost:8000/api/statistics/").mock(
            return_value=Response(200, json={"documents_total": 100, "documents_inbox": 5})
        )
        stats = await client.get_statistics()
        assert stats["documents_total"] == 100


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


class TestAuthHeader:
    @respx.mock
    async def test_auth_header(self, client):
        route = respx.get("http://localhost:8000/api/statistics/").mock(return_value=Response(200, json={}))
        await client.get_statistics()
        assert route.calls[0].request.headers["authorization"] == "Token test-token"


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------


class TestGetAllPages:
    @respx.mock
    async def test_single_page(self, client):
        respx.get("http://localhost:8000/api/tags/").mock(
            return_value=Response(200, json={"results": [{"id": 1, "name": "a"}], "next": None})
        )
        results = await client._get_all_pages("/api/tags/")
        assert len(results) == 1

    @respx.mock
    async def test_multi_page(self, client):
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Response(
                    200,
                    json={"results": [{"id": 1, "name": "a"}], "next": "http://localhost:8000/api/tags/?page=2"},
                )
            return Response(200, json={"results": [{"id": 2, "name": "b"}], "next": None})

        respx.get("http://localhost:8000/api/tags/").mock(side_effect=side_effect)
        results = await client._get_all_pages("/api/tags/")
        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2


# ---------------------------------------------------------------------------
# _parse_document
# ---------------------------------------------------------------------------


class TestParseDocument:
    def test_basic_parse(self, client):
        client._correspondents_cache = {1: "ACME"}
        client._doc_types_cache = {1: "Bill"}
        client._tags_cache = {1: "invoice"}
        doc = client._parse_document(_make_doc_response())
        assert doc.id == 42
        assert doc.title == "Test Invoice"
        assert doc.correspondent == "ACME"
        assert doc.document_type == "Bill"
        assert doc.tags == ["invoice"]

    def test_null_fields(self, client):
        client._correspondents_cache = {}
        client._doc_types_cache = {}
        client._tags_cache = {}
        data = _make_doc_response(correspondent=None, document_type=None)
        data["tags"] = []
        doc = client._parse_document(data)
        assert doc.correspondent is None
        assert doc.document_type is None
        assert doc.tags == []

    def test_unknown_tag_id(self, client):
        client._tags_cache = {}
        data = _make_doc_response(tags=[999])
        doc = client._parse_document(data)
        assert doc.tags == ["#999"]

    def test_content_truncation(self, client):
        client._correspondents_cache = {}
        client._doc_types_cache = {}
        client._tags_cache = {}
        long_content = "x" * 300
        data = _make_doc_response(content=long_content)
        doc = client._parse_document(data)
        assert doc.content.endswith("...")
        assert len(doc.content) == 203  # 200 + "..."

    def test_empty_content(self, client):
        client._correspondents_cache = {}
        client._doc_types_cache = {}
        client._tags_cache = {}
        data = _make_doc_response(content="")
        doc = client._parse_document(data)
        assert doc.content is None

    def test_missing_title(self, client):
        client._correspondents_cache = {}
        client._doc_types_cache = {}
        client._tags_cache = {}
        data = _make_doc_response()
        del data["title"]
        doc = client._parse_document(data)
        assert doc.title == "Untitled"

    def test_date_truncation(self, client):
        client._correspondents_cache = {}
        client._doc_types_cache = {}
        client._tags_cache = {}
        doc = client._parse_document(_make_doc_response())
        assert doc.created == "2025-01-15"
        assert doc.added == "2025-01-15"
