"""Tests for Paperless-NGX API client."""

import pytest
import respx
from httpx import Response

from paperless_bot.api.client import PaperlessClient


@pytest.fixture
def client():
    return PaperlessClient("http://localhost:8000", "test-token")


@pytest.fixture(autouse=True)
def _mock_api():
    with respx.mock:
        yield


@respx.mock
async def test_search_documents(client):
    respx.get("http://localhost:8000/api/tags/").mock(
        return_value=Response(200, json={"results": [{"id": 1, "name": "invoice"}], "next": None})
    )
    respx.get("http://localhost:8000/api/correspondents/").mock(
        return_value=Response(200, json={"results": [{"id": 1, "name": "ACME"}], "next": None})
    )
    respx.get("http://localhost:8000/api/document_types/").mock(
        return_value=Response(200, json={"results": [{"id": 1, "name": "Bill"}], "next": None})
    )
    respx.get("http://localhost:8000/api/documents/").mock(
        return_value=Response(
            200,
            json={
                "count": 1,
                "results": [
                    {
                        "id": 42,
                        "title": "Test Invoice",
                        "correspondent": 1,
                        "document_type": 1,
                        "tags": [1],
                        "created": "2025-01-15T00:00:00Z",
                        "added": "2025-01-15T12:00:00Z",
                        "content": "This is a test invoice content",
                    }
                ],
            },
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
async def test_upload_document(client):
    respx.post("http://localhost:8000/api/documents/post_document/").mock(
        return_value=Response(200, text='"abc-123-task-id"')
    )

    task_id = await client.upload_document(b"file content", "test.pdf")
    assert task_id == "abc-123-task-id"


@respx.mock
async def test_download_document(client):
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
async def test_get_tags(client):
    respx.get("http://localhost:8000/api/tags/").mock(
        return_value=Response(
            200,
            json={"results": [{"id": 1, "name": "invoice"}, {"id": 2, "name": "receipt"}], "next": None},
        )
    )

    tags = await client.get_tags()
    assert len(tags) == 2
    assert tags[0].name == "invoice"
    assert tags[1].name == "receipt"


@respx.mock
async def test_get_statistics(client):
    respx.get("http://localhost:8000/api/statistics/").mock(
        return_value=Response(200, json={"documents_total": 100, "documents_inbox": 5})
    )

    stats = await client.get_statistics()
    assert stats["documents_total"] == 100
    assert stats["documents_inbox"] == 5


@respx.mock
async def test_auth_header(client):
    route = respx.get("http://localhost:8000/api/statistics/").mock(return_value=Response(200, json={}))

    await client.get_statistics()
    assert route.calls[0].request.headers["authorization"] == "Token test-token"
