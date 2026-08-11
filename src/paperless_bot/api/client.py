"""
Async client for the Paperless-NGX REST API.
All Paperless API interaction goes through this module.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_DUPLICATE_DOC_ID_RE = re.compile(r"#(\d+)")

# Seconds before the tags/correspondents/document-types cache is considered
# stale and refreshed (items created in the Paperless web UI show up after
# at most this long instead of only after a bot restart).
CACHE_TTL = 5 * 60

# Consecutive task-poll failures before giving up early instead of sleeping
# out the whole upload timeout.
MAX_POLL_FAILURES = 5


def _raise_for_status_with_body(resp: httpx.Response) -> None:
    """raise_for_status, but keep Paperless's error body in the message.

    Paperless returns precise JSON diagnostics (e.g. '{"name": ["tag with
    this name already exists"]}') that a bare HTTPStatusError discards.
    """
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = resp.text.strip()
        if body:
            raise httpx.HTTPStatusError(
                f"{exc.args[0] if exc.args else exc}\nPaperless response: {body[:500]}",
                request=exc.request,
                response=exc.response,
            ) from None
        raise


@dataclass
class Document:
    """Represents a Paperless-NGX document."""

    id: int
    title: str
    correspondent: str | None
    document_type: str | None
    tags: list[str]
    created: str
    added: str
    content: str | None = None
    tag_ids: list[int] = field(default_factory=list)


@dataclass
class TaskResult:
    """Result of a Paperless-NGX upload task."""

    status: str  # "success", "duplicate", "failed", "timeout"
    doc_id: int | None = None
    message: str | None = None


@dataclass
class Tag:
    id: int
    name: str


@dataclass
class Correspondent:
    id: int
    name: str


@dataclass
class DocumentType:
    id: int
    name: str


class PaperlessClient:
    """Async HTTP client for Paperless-NGX API."""

    def __init__(self, base_url: str, token: str, *, inbox_tag_name: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
        )

        # Name resolution caches (ID -> name)
        self._tags_cache: dict[int, str] = {}
        self._correspondents_cache: dict[int, str] = {}
        self._doc_types_cache: dict[int, str] = {}
        self._inbox_tag_id: int | None = None
        self._inbox_tag_name_override = inbox_tag_name
        self._cache_loaded_at: float = 0.0

    async def close(self):
        await self._client.aclose()

    async def refresh_cache(self):
        """Populate/refresh name caches from Paperless API."""
        # Fetch raw tag data to access is_inbox_tag field
        raw_tags = await self._get_all_pages("/api/tags/")
        self._tags_cache = {t["id"]: t["name"] for t in raw_tags}

        correspondents = await self.get_correspondents()
        self._correspondents_cache = {c.id: c.name for c in correspondents}
        doc_types = await self.get_document_types()
        self._doc_types_cache = {dt.id: dt.name for dt in doc_types}

        # Auto-detect inbox tag:
        # 1. If explicit name override is set, find by name
        # 2. Otherwise, find the tag with is_inbox_tag=true from the API
        self._inbox_tag_id = None
        if self._inbox_tag_name_override:
            for t in raw_tags:
                if t["name"].lower() == self._inbox_tag_name_override.lower():
                    self._inbox_tag_id = t["id"]
                    break
            if self._inbox_tag_id:
                logger.info(
                    "Inbox tag found by name override: %s (id=%d)", self._inbox_tag_name_override, self._inbox_tag_id
                )
            else:
                logger.warning("INBOX_TAG='%s' not found in Paperless", self._inbox_tag_name_override)
        else:
            for t in raw_tags:
                if t.get("is_inbox_tag"):
                    self._inbox_tag_id = t["id"]
                    logger.info("Inbox tag auto-detected: %s (id=%d)", t["name"], t["id"])
                    break

        logger.info(
            "Cache refreshed: %d tags, %d correspondents, %d document types (inbox_tag_id=%s)",
            len(self._tags_cache),
            len(self._correspondents_cache),
            len(self._doc_types_cache),
            self._inbox_tag_id,
        )
        self._cache_loaded_at = time.monotonic()

    async def _ensure_cache(self):
        """Populate the caches if empty; refresh them when older than CACHE_TTL."""
        fresh = self._tags_cache and time.monotonic() - self._cache_loaded_at <= CACHE_TTL
        if fresh:
            return
        try:
            await self.refresh_cache()
        except Exception:
            if not self._tags_cache:
                raise
            # A populated-but-stale cache beats failing the user's request
            logger.warning("Cache refresh failed; serving stale metadata cache", exc_info=True)
            self._cache_loaded_at = time.monotonic()

    # --- Documents ---

    async def search_documents(self, query: str, page: int = 1, page_size: int = 10) -> tuple[list[Document], int]:
        """Full-text search. Returns (documents, total_count)."""
        await self._ensure_cache()
        resp = await self._client.get(
            "/api/documents/",
            params={"query": query, "page": page, "page_size": page_size},
        )
        _raise_for_status_with_body(resp)
        data = resp.json()
        documents = [self._parse_document(d) for d in data["results"]]
        return documents, data["count"]

    async def get_recent_documents(self, page_size: int = 10) -> list[Document]:
        """Get most recently added documents."""
        await self._ensure_cache()
        resp = await self._client.get(
            "/api/documents/",
            params={"ordering": "-added", "page_size": page_size},
        )
        _raise_for_status_with_body(resp)
        return [self._parse_document(d) for d in resp.json()["results"]]

    async def get_document(self, doc_id: int) -> Document:
        """Get a single document by ID."""
        await self._ensure_cache()
        resp = await self._client.get(f"/api/documents/{doc_id}/")
        _raise_for_status_with_body(resp)
        return self._parse_document(resp.json())

    async def get_document_tag_ids(self, doc_id: int) -> list[int]:
        """Get the current tag IDs of a document (fresh, not from cache)."""
        resp = await self._client.get(f"/api/documents/{doc_id}/")
        _raise_for_status_with_body(resp)
        return list(resp.json().get("tags", []))

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        title: str | None = None,
        correspondent: int | None = None,
        document_type: int | None = None,
        tags: list[int] | None = None,
    ) -> str:
        """Upload a document. Returns the task ID from Paperless."""
        data: dict[str, str | list[str]] = {}
        if title:
            data["title"] = title
        if correspondent:
            data["correspondent"] = str(correspondent)
        if document_type:
            data["document_type"] = str(document_type)
        if tags:
            data["tags"] = [str(t) for t in tags]

        resp = await self._client.post(
            "/api/documents/post_document/",
            files={"document": (filename, file_bytes)},
            data=data,
        )
        _raise_for_status_with_body(resp)
        return resp.text.strip().strip('"')

    async def wait_for_task(self, task_id: str, timeout: int = 60) -> TaskResult:
        """Poll for an upload task to complete. Returns a TaskResult.

        Handles both Paperless-NGX task API shapes:
        - 2.x (API <= v9): bare list, uppercase Celery statuses, ``result`` string
          and ``related_document`` fields.
        - 3.x (API >= v10): paginated ``{"results": [...]}`` envelope, lowercase
          statuses, and a ``result_data`` dict (``document_id``, ``duplicate_of``,
          ``reason``, ``error_message``).
        """
        poll_failures = 0
        for _ in range(timeout // 2):
            await asyncio.sleep(2)
            try:
                resp = await self._client.get("/api/tasks/", params={"task_id": task_id})
                _raise_for_status_with_body(resp)
                data = resp.json()
                poll_failures = 0
                # dict: 3.x paginated envelope, or (defensively) a bare task dict
                tasks = data.get("results", [data]) if isinstance(data, dict) else data
                if tasks:
                    task = tasks[0]
                    status = str(task.get("status") or "").upper()
                    result_data = task.get("result_data") or {}
                    result_msg = str(
                        task.get("result") or result_data.get("reason") or result_data.get("error_message") or ""
                    )

                    if status == "SUCCESS":
                        return TaskResult(
                            status="success",
                            doc_id=self._extract_task_doc_id(task),
                        )

                    if status in ("FAILURE", "REVOKED"):
                        # Detect duplicate uploads
                        duplicate_of = result_data.get("duplicate_of")
                        if duplicate_of or "duplicate" in result_msg.lower():
                            existing_id = int(duplicate_of) if duplicate_of else self._extract_duplicate_id(result_msg)
                            return TaskResult(
                                status="duplicate",
                                doc_id=existing_id,
                                message=result_msg or f"Duplicate of document #{existing_id}",
                            )
                        logger.error("Task %s failed: %s", task_id, result_msg)
                        return TaskResult(status="failed", message=result_msg)

            except Exception:
                poll_failures += 1
                logger.warning("Error polling task %s (%d consecutive)", task_id, poll_failures, exc_info=True)
                if poll_failures >= MAX_POLL_FAILURES:
                    # The API is unreachable or rejecting us — sleeping out the
                    # rest of the timeout would only delay the same answer.
                    logger.error("Aborting task %s polling after %d consecutive errors", task_id, poll_failures)
                    return TaskResult(
                        status="failed",
                        message="Could not check processing status (Paperless task API unreachable or rejecting requests). The document may still be processed.",
                    )

        logger.warning("Task %s did not finish within %d seconds", task_id, timeout)
        return TaskResult(status="timeout")

    @staticmethod
    def _extract_task_doc_id(task: dict) -> int | None:
        """Extract the created document ID from a completed task (2.x or 3.x shape)."""
        doc_id = task.get("related_document")
        if doc_id is None:
            doc_id = (task.get("result_data") or {}).get("document_id")
        if doc_id is None:
            related_ids = task.get("related_document_ids") or []
            doc_id = related_ids[0] if related_ids else None
        try:
            return int(doc_id) if doc_id is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_duplicate_id(result_msg: str) -> int | None:
        """Extract the existing document ID from a duplicate failure message.

        Paperless returns messages like:
          'Not consuming file.pdf: It is a duplicate of Invoice April (#42).'
        """
        match = _DUPLICATE_DOC_ID_RE.search(result_msg)
        if match:
            return int(match.group(1))
        return None

    async def download_document(self, doc_id: int) -> tuple[bytes, str]:
        """Download a document. Returns (file_bytes, filename)."""
        resp = await self._client.get(f"/api/documents/{doc_id}/download/")
        _raise_for_status_with_body(resp)
        cd = resp.headers.get("content-disposition", "")
        filename = f"document_{doc_id}.pdf"
        if "filename=" in cd:
            # Handle both filename="name" and filename*=UTF-8''name
            parts = cd.split("filename=")
            if len(parts) > 1:
                filename = parts[1].split(";")[0].strip('"').strip("'")
        return resp.content, filename

    async def update_document(self, doc_id: int, **fields) -> Document:
        """Partial update of a document (tags, correspondent, document_type, title, etc.)."""
        await self._ensure_cache()
        resp = await self._client.patch(f"/api/documents/{doc_id}/", json=fields)
        _raise_for_status_with_body(resp)
        return self._parse_document(resp.json())

    async def get_inbox_documents(self, page_size: int = 10) -> tuple[list[Document], int]:
        """Get documents with the inbox tag."""
        await self._ensure_cache()
        if not self._inbox_tag_id:
            return [], 0
        resp = await self._client.get(
            "/api/documents/",
            params={"tags__id": self._inbox_tag_id, "ordering": "-added", "page_size": page_size},
        )
        _raise_for_status_with_body(resp)
        data = resp.json()
        return [self._parse_document(d) for d in data["results"]], data["count"]

    async def remove_inbox_tag(self, doc_id: int) -> None:
        """Remove the Inbox tag from a document if it has one."""
        await self._ensure_cache()
        if not self._inbox_tag_id:
            return
        resp = await self._client.get(f"/api/documents/{doc_id}/")
        _raise_for_status_with_body(resp)
        current_tags = resp.json().get("tags", [])
        if self._inbox_tag_id in current_tags:
            current_tags.remove(self._inbox_tag_id)
            await self._client.patch(f"/api/documents/{doc_id}/", json={"tags": current_tags})
            logger.info("Removed Inbox tag from document %d", doc_id)

    # --- Tags ---

    async def get_tags(self) -> list[Tag]:
        """Get all tags."""
        results = await self._get_all_pages("/api/tags/")
        return [Tag(id=t["id"], name=t["name"]) for t in results]

    async def create_tag(self, name: str) -> Tag:
        """Create a new tag. Returns the created Tag."""
        resp = await self._client.post("/api/tags/", json={"name": name})
        _raise_for_status_with_body(resp)
        data = resp.json()
        tag = Tag(id=data["id"], name=data["name"])
        self._tags_cache[tag.id] = tag.name
        return tag

    # --- Correspondents ---

    async def get_correspondents(self) -> list[Correspondent]:
        """Get all correspondents."""
        results = await self._get_all_pages("/api/correspondents/")
        return [Correspondent(id=c["id"], name=c["name"]) for c in results]

    async def create_correspondent(self, name: str) -> Correspondent:
        """Create a new correspondent. Returns the created Correspondent."""
        resp = await self._client.post("/api/correspondents/", json={"name": name})
        _raise_for_status_with_body(resp)
        data = resp.json()
        corr = Correspondent(id=data["id"], name=data["name"])
        self._correspondents_cache[corr.id] = corr.name
        return corr

    # --- Document Types ---

    async def get_document_types(self) -> list[DocumentType]:
        """Get all document types."""
        results = await self._get_all_pages("/api/document_types/")
        return [DocumentType(id=dt["id"], name=dt["name"]) for dt in results]

    async def create_document_type(self, name: str) -> DocumentType:
        """Create a new document type. Returns the created DocumentType."""
        resp = await self._client.post("/api/document_types/", json={"name": name})
        _raise_for_status_with_body(resp)
        data = resp.json()
        dt = DocumentType(id=data["id"], name=data["name"])
        self._doc_types_cache[dt.id] = dt.name
        return dt

    # --- Stats ---

    async def get_statistics(self) -> dict:
        """Get Paperless-NGX statistics."""
        resp = await self._client.get("/api/statistics/")
        _raise_for_status_with_body(resp)
        return resp.json()

    async def probe(self) -> dict[str, str]:
        """Validate connectivity and auth against Paperless; return server info.

        Raises on unreachable host or rejected token. The version headers are
        logged so API-shape changes (like the 2.x -> 3.x tasks change) are
        visible in startup logs. Deliberately NOT pinning an Accept version:
        older servers 406 unsupported versions, and the client already parses
        both known task shapes.
        """
        resp = await self._client.get("/api/statistics/")
        _raise_for_status_with_body(resp)
        return {
            "server_version": resp.headers.get("x-version", "unknown"),
            "api_version": resp.headers.get("x-api-version", "unknown"),
        }

    # --- Helpers ---

    async def _get_all_pages(self, endpoint: str) -> list[dict]:
        """Fetch all pages of a paginated endpoint."""
        results = []
        page = 1
        while True:
            resp = await self._client.get(endpoint, params={"page": page, "page_size": 100})
            _raise_for_status_with_body(resp)
            data = resp.json()
            results.extend(data["results"])
            if not data.get("next"):
                break
            page += 1
        return results

    def _parse_document(self, data: dict) -> Document:
        """Parse raw API document dict into Document dataclass."""
        # Resolve correspondent name
        corr_id = data.get("correspondent")
        correspondent = self._correspondents_cache.get(corr_id) if corr_id else None

        # Resolve document type name
        dt_id = data.get("document_type")
        document_type = self._doc_types_cache.get(dt_id) if dt_id else None

        # Resolve tag names
        tag_ids = data.get("tags", [])
        tags = [self._tags_cache.get(tid, f"#{tid}") for tid in tag_ids]

        # Content snippet (truncate for display)
        content = data.get("content", "")
        if content and len(content) > 200:
            content = content[:200] + "..."

        return Document(
            id=data["id"],
            title=data.get("title", "Untitled"),
            correspondent=correspondent,
            document_type=document_type,
            tags=tags,
            created=data.get("created", "")[:10],
            added=data.get("added", "")[:10],
            content=content or None,
            tag_ids=list(tag_ids),
        )
