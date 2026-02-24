# Paperless Telegram Bot

[![Docker Image](https://img.shields.io/docker/v/drumsergio/paperless-telegram-bot?sort=semver&label=Docker%20Hub)](https://hub.docker.com/r/drumsergio/paperless-telegram-bot)
[![Tests](https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/tests.yml)
[![Lint](https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/lint.yml/badge.svg)](https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/lint.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Manage your [Paperless-NGX](https://github.com/paperless-ngx/paperless-ngx) documents directly from Telegram. Upload files, search by content, organize metadata, review your inbox, and download documents -- all from your phone.

## Features

- **Upload documents and photos** -- send any file or photo to the bot, and it gets uploaded to Paperless-NGX automatically
- **Full-text search** -- search your entire document library with paginated results; just type a query or use `/search`
- **Metadata management** -- assign tags, correspondents, and document types right after uploading, with paginated selection keyboards
- **Create metadata inline** -- create new tags, correspondents, or document types on the fly without leaving the chat
- **Inbox review workflow** -- browse documents in your Paperless inbox, mark them as reviewed, and remove the inbox tag with one tap
- **Download documents** -- download any document directly to Telegram (up to 50 MB)
- **Statistics** -- quick overview of your Paperless-NGX instance (document count, inbox size, tags, correspondents, document types)
- **Duplicate detection** -- if you upload a file that already exists, the bot tells you and links to the existing document
- **Access control** -- restrict the bot to specific Telegram user IDs
- **Health check endpoint** -- built-in HTTP `/health` endpoint for Docker health checks and monitoring
- **Configurable inbox tag** -- auto-detects the inbox tag from Paperless, or lets you specify one explicitly

## Quick Start

### Docker Compose (recommended)

```yaml
services:
  paperless-telegram-bot:
    image: drumsergio/paperless-telegram-bot:0.6.0
    restart: unless-stopped
    environment:
      TELEGRAM_BOT_TOKEN: "your-bot-token"
      PAPERLESS_URL: "http://paperless:8000"
      PAPERLESS_TOKEN: "your-paperless-api-token"
      TELEGRAM_ALLOWED_USERS: "123456789"  # your Telegram user ID
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
      interval: 30s
      timeout: 5s
      start-period: 10s
      retries: 3
```

### Docker Run

```bash
docker run -d \
  --name paperless-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your-bot-token" \
  -e PAPERLESS_URL="http://paperless:8000" \
  -e PAPERLESS_TOKEN="your-paperless-api-token" \
  -e TELEGRAM_ALLOWED_USERS="123456789" \
  drumsergio/paperless-telegram-bot:0.6.0
```

### Getting Your Tokens

1. **Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram, create a new bot with `/newbot`, and copy the token
2. **Paperless API Token**: In Paperless-NGX, go to Settings > API Tokens (or `http://your-paperless/admin/authtoken/tokenproxy/`)
3. **Your Telegram User ID**: Message [@userinfobot](https://t.me/userinfobot) on Telegram to get your numeric ID

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token from BotFather |
| `PAPERLESS_URL` | URL of your Paperless-NGX instance (e.g., `http://paperless:8000`) |
| `PAPERLESS_TOKEN` | Paperless-NGX API authentication token |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_ALLOWED_USERS` | *(empty = open to anyone)* | Comma-separated Telegram user IDs allowed to use the bot |
| `PAPERLESS_PUBLIC_URL` | same as `PAPERLESS_URL` | User-facing URL for clickable document links (useful when the internal URL differs from the external one) |
| `MAX_SEARCH_RESULTS` | `10` | Number of results per page in search, recent, and inbox listings |
| `REMOVE_INBOX_ON_DONE` | `true` | Remove the inbox tag when the user clicks "Done" after setting metadata. Set to `false` to disable |
| `INBOX_TAG` | *(auto-detect)* | Explicit inbox tag name. If unset, auto-detects the tag with `is_inbox_tag=true` from the Paperless API |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HEALTH_PORT` | `8080` | Port for the `/health` HTTP endpoint |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/search <query>` | Full-text search across all documents |
| `/recent` | List recently added documents |
| `/inbox` | List documents in the inbox with review buttons |
| `/stats` | Show Paperless-NGX statistics |
| `/help` | Show available commands |

You can also just type any text (without a command) to search.

## Usage

### Uploading Documents

Send any file (PDF, image, etc.) or photo directly to the bot. After Paperless finishes processing:

1. The bot shows the document title and offers a metadata keyboard
2. **Set Tags** -- paginated checkbox list; select multiple, create new ones inline
3. **Set Correspondent** -- paginated single-select list; create new ones inline
4. **Set Document Type** -- paginated single-select list; create new ones inline
5. **Done** -- saves metadata and provides a direct link to the document in Paperless

If the file is a duplicate, the bot detects it and shows a link to the existing document instead.

### Searching

Use `/search invoice` or simply type `invoice` as a message. Results are paginated and each document has a download button.

### Inbox Workflow

The bot integrates with Paperless-NGX's inbox tag system:

1. Paperless automatically tags new documents with the inbox tag (configured server-side via `is_inbox_tag=true` on a tag)
2. Use `/inbox` to list all documents still in the inbox
3. Each inbox document shows **Download** and **Reviewed** buttons
4. Clicking **Reviewed** removes the inbox tag from the document
5. The inbox tag is hidden from the tag selection keyboard since it is auto-managed

The bot auto-detects your inbox tag from the Paperless API. If you use a custom tag name, set `INBOX_TAG` explicitly. If you don't use an inbox workflow at all, set `REMOVE_INBOX_ON_DONE=false` -- all inbox features will silently degrade.

## Development

### Prerequisites

- Python 3.11+
- A running Paperless-NGX instance

### Setup

```bash
git clone https://github.com/GeiserX/paperless-telegram-bot.git
cd paperless-telegram-bot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Locally

```bash
cp .env.example .env
# Edit .env with your tokens
paperless-bot run
```

### Testing

```bash
pytest tests/ -v
```

### Linting & Formatting

```bash
ruff check src/
ruff format src/
```

Pre-commit hooks are configured to run ruff automatically:

```bash
pre-commit install
```

### Project Structure

```
src/paperless_bot/
├── __init__.py          # Version
├── __main__.py          # Entry point, CLI, health server
├── config.py            # Environment variable loading
├── api/
│   └── client.py        # Async Paperless-NGX API client
└── bot/
    ├── handlers.py      # Telegram command and callback handlers
    └── keyboards.py     # Inline keyboard builders
```

## Architecture

- **Telegram bot** -- built with [python-telegram-bot](https://python-telegram-bot.org/), uses long polling
- **Paperless API client** -- async HTTP client using [httpx](https://www.python-encode.org/httpx/), with in-memory caching of tags/correspondents/document types
- **Health endpoint** -- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) running in a background daemon thread on port 8080
- **CI/CD** -- GitHub Actions runs linting and tests on every push/PR; Docker images are built and pushed to Docker Hub on tag pushes and main branch merges

## License

[GPL-3.0](LICENSE)
