# CLAUDE.md — paperless-telegram-bot

## Overview
Full-featured Telegram bot for managing Paperless-NGX documents entirely through chat -- upload files, search the archive with full-text search, manage metadata (tags, correspondents, document types), review inbox, and download documents.

## Tech Stack
- Python 3.11+
- python-telegram-bot (Telegram Bot API)
- httpx (async HTTP client for Paperless-NGX API)
- FastAPI + uvicorn (health check endpoint)
- Docker (non-root container)
- ruff (linter + formatter)
- pytest + pytest-asyncio + respx (testing)
- pre-commit hooks
- PyPI package (`paperless-telegram-bot`)
- GitHub Actions CI

## Development
```bash
pip install -r requirements.txt
python -m src.paperless_bot      # Run the bot

# Lint and format
ruff check src/
ruff format src/

# Tests
python3 -m pytest tests/ -v

# Pre-commit
pre-commit run --all-files
```

## Architecture
- `src/paperless_bot/bot/handlers.py` — Telegram bot logic, command handlers, callback routing, inbox review flow
- `src/paperless_bot/api/client.py` — Paperless-NGX API client, caching, inbox tag auto-detection
- `src/paperless_bot/bot/keyboards.py` — Inline keyboard builders (metadata, tag selection, inbox with review buttons)
- `src/paperless_bot/config.py` — Environment variables and configuration
- `src/paperless_bot/__main__.py` — Entry point, health server, CLI
- `tests/` — pytest test suite (`test_client.py` and `test_config.py` are maintained; `test_handlers.py` is stale)
- `docs/ROADMAP.md` — Planned features and future improvements
- `Dockerfile` — Non-root Docker container
- `pyproject.toml` — Package metadata and build config
- `.env.example` — Required environment variables template

## Git Workflow
- Create feature branches and submit pull requests
- Do NOT commit directly to main branch
- Descriptive branch names (e.g., `feat/batch-upload`, `fix/search-pagination`)
- Squash merge PRs to keep main history clean

## Deployment

### Versioning Rules
- **NEVER** reuse or force-retag an existing version. Tags only go forward.
- **Patch** (`v0.6.0` -> `v0.6.1`): Bug fixes, small tweaks
- **Minor** (`v0.6.x` -> `v0.7.0`): New features, significant behavior changes
- **Major** (`v0.x.y` -> `v1.0.0`): Breaking changes
- Check the latest tag before tagging: `git describe --tags --abbrev=0`
- Update version in both `pyproject.toml` and `src/paperless_bot/__init__.py`
- Also update the image tag in `gitea/geiserback/paperless-telegram-bot/docker-compose.yml` to match

### Release Steps
1. Create feature branch, push, open PR, squash-merge to `main`
2. Create a GitHub release via `gh release create vX.Y.Z --target main` (GHA triggers on release tags)
3. **Wait for GHA `docker-publish.yml` to complete** -- verify the run succeeds before proceeding
4. Update `gitea/geiserback/paperless-telegram-bot/docker-compose.yml` with the new tag, commit and push to Gitea
5. Redeploy via Portainer API on **geiserback** (stack ID `80`, endpoint `2`)
6. Verify with `docker ps --filter name=paperless_telegram_bot` and check logs for `Bot commands registered`

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `PAPERLESS_URL` | Internal Paperless-NGX URL (e.g., `http://192.168.10.110:8000`) |
| `PAPERLESS_TOKEN` | Paperless-NGX API token |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_ALLOWED_USERS` | *(empty = open)* | Comma-separated Telegram user IDs allowed to use the bot |
| `PAPERLESS_PUBLIC_URL` | `PAPERLESS_URL` | User-facing URL for clickable document links (e.g., Tailscale hostname) |
| `MAX_SEARCH_RESULTS` | `10` | Number of results per page in search/recent/inbox |
| `REMOVE_INBOX_ON_DONE` | `true` | Remove inbox tag when user clicks "Done" in metadata flow. Set `false` to disable |
| `INBOX_TAG` | *(auto-detect)* | Explicit inbox tag name override. If unset, auto-detects the tag with `is_inbox_tag=true` from Paperless API |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HEALTH_PORT` | `8080` | Port for the `/health` HTTP endpoint |

## Key Architecture Decisions

### Bot Commands
Registered via `set_my_commands` in `post_init` callback: `/search`, `/recent`, `/inbox`, `/stats`, `/help`.

### Callback Data Encoding
Telegram's `callback_data` has a **64-byte limit**. All callback prefixes are kept short:

| Prefix | Purpose |
|--------|---------|
| `meta:tags:`, `meta:corr:`, `meta:dtype:`, `meta:done:` | Metadata menu actions |
| `tag:x:`, `tag:o:` | Tag toggle (checked/unchecked) |
| `tagp:`, `tagok:` | Tag pagination, confirm |
| `newtag:`, `newcorr:`, `newdtype:` | Create new metadata item |
| `ccr:` | Cancel create |
| `corr:`, `corrp:` | Correspondent select, paginate |
| `dtype:`, `dtypep:` | Document type select, paginate |
| `dl:` | Download document |
| `sp:` | Search pagination |
| `rev:` | Mark as reviewed (remove inbox tag) |

Search queries are stored in a per-chat dict (`search_queries`) since they'd exceed the 64-byte limit.

### Inbox Workflow
The bot supports an optional "inbox review" pattern common in the Paperless community:

1. **Detection:** On cache refresh, the client finds the inbox tag by checking the Paperless API `is_inbox_tag` field (not name matching). Alternatively, `INBOX_TAG` env var provides an explicit name override.
2. **Auto-tagging:** Paperless auto-adds the inbox tag to all new documents (configured server-side via `is_inbox_tag=true` on the tag).
3. **Review:** `/inbox` command shows documents with the inbox tag, each with "Download" and "Reviewed" buttons.
4. **Completion:** Clicking "Done" in metadata flow or "Reviewed" in inbox listing removes the inbox tag from the document.
5. **Hiding:** The inbox tag is excluded from the tag selection keyboard (`_user_visible_tags()`) since it's auto-managed.
6. **Opt-out:** Users who don't use an inbox tag can set `REMOVE_INBOX_ON_DONE=false`. If no inbox tag exists, all inbox features silently degrade.

### Metadata Caching
Tags, correspondents, and document types are cached in `PaperlessClient` as `dict[int, str]` (ID -> name). Cache is populated lazily on first API call via `_ensure_cache()` and can be refreshed explicitly. The inbox tag ID is also resolved during cache refresh.

### Duplicate Detection
Upload tasks that fail with "duplicate" in the result message are handled specially -- the bot extracts the existing document ID via regex and shows a link to the duplicate.

### Health Check
FastAPI on port 8080 serves `/health` endpoint. Docker HEALTHCHECK polls it every 30s. Runs in a background daemon thread.

## Key Rules
- Never hardcode tokens or credentials; use environment variables (see `.env.example`)
- Docker image published to Docker Hub as `drumsergio/paperless-telegram-bot` with semver tags
- Also published to PyPI; keep `pyproject.toml` version in sync
- User authorization via `TELEGRAM_ALLOWED_USERS` allowlist is mandatory
- Runs as unprivileged user inside Docker container
- Use `_safe_edit()` wrapper for all Telegram message edits (handles BadRequest, TimedOut, NetworkError)
- Use `%s` formatting (not f-strings) in log calls; prefer f-strings elsewhere

## Code Style
- Follow PEP 8, use type hints
- Logging: `logger = logging.getLogger(__name__)`
- Linter/Formatter: always run `ruff check` and `ruff format` before committing

## Boundaries

### Always (do without asking)
- Create new files, change dependencies, modify Docker config, update docs/README, change env vars

### Ask First
- Delete files, change Paperless-NGX API contracts, modify callback_data encoding scheme (64-byte limit is strict)

### Never
- Modify .env files or secrets, force push to git, reuse existing version tags, expose tokens in logs

*Generated by [LynxPrompt](https://lynxprompt.com) CLI*
