<p align="center">
  <img src="https://raw.githubusercontent.com/GeiserX/paperless-telegram-bot/main/docs/images/banner.svg" alt="paperless-telegram-bot banner" width="900"/>
</p>

<p align="center">
  <strong>Manage Paperless-NGX documents entirely through Telegram.</strong>
</p>

<p align="center">
  <a href="https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/docker-publish.yml"><img src="https://img.shields.io/github/actions/workflow/status/GeiserX/paperless-telegram-bot/docker-publish.yml?style=flat-square&logo=github&label=build" alt="Docker Build"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/GeiserX/paperless-telegram-bot/tests.yml?style=flat-square&logo=github&label=tests" alt="Tests"></a>
  <a href="https://hub.docker.com/r/drumsergio/paperless-telegram-bot"><img src="https://img.shields.io/docker/pulls/drumsergio/paperless-telegram-bot?style=flat-square&logo=docker" alt="Docker Pulls"></a>
  <a href="https://pypi.org/project/paperless-telegram-bot/"><img src="https://img.shields.io/pypi/v/paperless-telegram-bot?style=flat-square&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/GeiserX/paperless-telegram-bot?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <a href="https://codecov.io/gh/GeiserX/paperless-telegram-bot"><img src="https://codecov.io/gh/GeiserX/paperless-telegram-bot/graph/badge.svg" alt="codecov"></a>
</p>

---

A full-featured Telegram bot that integrates with [Paperless-NGX](https://docs.paperless-ngx.com/), giving you complete document management from your phone or desktop -- no web UI required. Upload documents and photos, search your archive with full-text search, manage metadata, review your inbox, and download files, all within Telegram.

## Features

- **Document Upload** -- Send any file or photo to the bot and it gets uploaded to Paperless-NGX automatically. Duplicates are detected and linked.
- **Full-Text Search** -- Search across all your documents with `/search`. Results are paginated with inline keyboard navigation.
- **Metadata Management** -- After uploading (or on any document), assign tags, correspondents, and document types through interactive inline keyboards.
- **Inbox Review** -- `/inbox` lists all documents tagged with your inbox tag. Mark them as reviewed with a single tap.
- **Document Download** -- Download original files directly to Telegram (up to 50 MB).
- **Recent Documents** -- `/recent` shows the latest documents added to your archive.
- **System Statistics** -- `/stats` displays document counts, tag usage, and storage information.
- **Health Endpoint** -- Built-in `/health` HTTP endpoint for Docker health checks and monitoring.
- **User Authorization** -- Restrict bot access to specific Telegram user IDs via allowlist.
- **Non-Root Docker** -- Runs as an unprivileged user inside the container.

## Quick Start

### Docker (Recommended)

```bash
docker run -d \
  --name paperless-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_bot_token \
  -e PAPERLESS_URL=http://your-paperless:8000 \
  -e PAPERLESS_TOKEN=your_api_token \
  -e TELEGRAM_ALLOWED_USERS=123456789 \
  drumsergio/paperless-telegram-bot:latest
```

### Docker Compose

```yaml
services:
  paperless-telegram-bot:
    image: drumsergio/paperless-telegram-bot:latest
    container_name: paperless-telegram-bot
    restart: unless-stopped
    environment:
      TELEGRAM_BOT_TOKEN: "${TELEGRAM_BOT_TOKEN}"
      PAPERLESS_URL: "http://paperless:8000"
      PAPERLESS_TOKEN: "${PAPERLESS_TOKEN}"
      TELEGRAM_ALLOWED_USERS: "${TELEGRAM_ALLOWED_USERS}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### Manual Installation

```bash
git clone https://github.com/GeiserX/paperless-telegram-bot.git
cd paperless-telegram-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Edit with your values
python -m paperless_bot run
```

## Configuration

All configuration is done through environment variables. Copy `.env.example` to `.env` for local development.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram Bot API token from [@BotFather](https://t.me/BotFather) |
| `PAPERLESS_URL` | Yes | -- | Paperless-NGX instance URL (e.g. `http://localhost:8000`) |
| `PAPERLESS_TOKEN` | Yes | -- | Paperless-NGX API authentication token |
| `TELEGRAM_ALLOWED_USERS` | No | *(open)* | Comma-separated Telegram user IDs allowed to use the bot |
| `PAPERLESS_PUBLIC_URL` | No | `PAPERLESS_URL` | User-facing URL for clickable document links |
| `MAX_SEARCH_RESULTS` | No | `10` | Number of results per page in search, recent, and inbox |
| `REMOVE_INBOX_ON_DONE` | No | `true` | Remove inbox tag when clicking "Done" in metadata flow |
| `INBOX_TAG` | No | *(auto-detect)* | Explicit inbox tag name. If unset, auto-detects via Paperless API |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HEALTH_PORT` | No | `8080` | Port for the `/health` HTTP endpoint |

## Commands

| Command | Description |
|---------|-------------|
| `/search <query>` | Full-text search across all documents |
| `/recent` | Show recently added documents |
| `/inbox` | List documents in the inbox with review actions |
| `/stats` | Display Paperless-NGX statistics |
| `/help` | Show available commands and usage |

In addition to commands, you can send any **file or photo** directly to the bot to upload it to Paperless-NGX. After upload, an interactive keyboard lets you assign tags, a correspondent, and a document type.

## Architecture

```
paperless-telegram-bot
|-- src/paperless_bot/
|   |-- __main__.py         # Entry point, health server, CLI
|   |-- config.py           # Environment variable loading and validation
|   |-- api/
|   |   +-- client.py       # Async Paperless-NGX API client with caching
|   +-- bot/
|       |-- handlers.py     # Command handlers, callback routing, upload flow
|       +-- keyboards.py    # Inline keyboard builders for metadata selection
+-- tests/                  # pytest + respx test suite
```

**Key design decisions:**

- **Async throughout** -- Uses `python-telegram-bot` with `httpx` for fully asynchronous I/O.
- **Metadata caching** -- Tags, correspondents, and document types are cached in memory and refreshed on demand, minimizing API calls.
- **Callback data encoding** -- Telegram limits `callback_data` to 64 bytes. All prefixes are kept short (`meta:tags:`, `dl:`, `sp:`, etc.) and long search queries are stored server-side per chat.
- **Inbox auto-detection** -- The bot reads the `is_inbox_tag` field from the Paperless API rather than matching by name, so it works with any language or custom tag name.
- **Duplicate handling** -- Upload failures containing "duplicate" are parsed to extract and link to the existing document.

## Security

- **User allowlist** -- Set `TELEGRAM_ALLOWED_USERS` to restrict access. When empty, the bot accepts messages from anyone (not recommended for production).
- **Non-root container** -- The Docker image runs as an unprivileged `paperlessbot` user (UID 1000).
- **No secrets in code** -- All credentials are loaded from environment variables. Never commit `.env` files.
- **API token scoping** -- The bot uses a single Paperless-NGX API token. Create a dedicated user/token with appropriate permissions.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter and formatter
ruff check src/ && ruff format src/

# Run tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=paperless_bot --cov-report=term-missing
```

## More Telegram Tools

| Project | Description |
|---------|-------------|
| [Telegram-Archive](https://github.com/GeiserX/Telegram-Archive) | Automated incremental Telegram backups with local web viewer |
| [AskePub](https://github.com/GeiserX/AskePub) | Telegram bot for ePub annotation with GPT-4 |
| [telegram-delay-channel-cloner](https://github.com/GeiserX/telegram-delay-channel-cloner) | Relay messages between channels with configurable delay |
| [jellyfin-telegram-channel-sync](https://github.com/GeiserX/jellyfin-telegram-channel-sync) | Sync Jellyfin access with Telegram channel membership |
| [telegram-slskd-local-bot](https://github.com/GeiserX/telegram-slskd-local-bot) | Automated music discovery and download via Telegram |


## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`feat/my-feature` or `fix/my-bug`)
3. Follow the existing code style (enforced by `ruff`)
4. Add tests for new functionality
5. Submit a pull request

This project follows [Conventional Commits](https://conventionalcommits.org) and [Semantic Versioning](https://semver.org).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
