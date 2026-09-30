# Configuration

All configuration is done through environment variables. Copy `.env.example` to `.env` for local development.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram Bot API token from [@BotFather](https://t.me/BotFather) |
| `PAPERLESS_URL` | Yes | -- | Paperless-ngx instance URL (e.g. `http://localhost:8000`) |
| `PAPERLESS_TOKEN` | Yes | -- | Paperless-ngx API authentication token |
| `TELEGRAM_ALLOWED_USERS` | Yes* | -- | Comma-separated Telegram user IDs allowed to use the bot. *Required unless `ALLOW_OPEN_ACCESS=true`; an empty allowlist refuses to start |
| `ALLOW_OPEN_ACCESS` | No | `false` | Explicit opt-in to run **without** an allowlist (open to any Telegram user) |
| `PAPERLESS_PUBLIC_URL` | No | `PAPERLESS_URL` | User-facing URL for clickable document links |
| `MAX_SEARCH_RESULTS` | No | `10` | Number of results per page in search, recent, and inbox |
| `UPLOAD_TASK_TIMEOUT` | No | `300` | Seconds to wait for Paperless to finish processing an upload (increase if slow tasks such as mail checks block the consume queue) |
| `REMOVE_INBOX_ON_DONE` | No | `true` | Remove inbox tag when clicking "Done" in metadata flow |
| `INBOX_TAG` | No | *(auto-detect)* | Explicit inbox tag name. If unset, auto-detects via Paperless API |
| `DROP_PENDING_UPDATES` | No | `false` | Discard Telegram updates that arrived while the bot was down instead of processing them on startup |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HEALTH_PORT` | No | `8080` | Port for the `/health` HTTP endpoint (returns `503 degraded` when Paperless is unreachable) |

Compatible with Paperless-ngx **2.x and 3.x** (both task-API response formats are handled).

## Security

- **User allowlist** -- Set `TELEGRAM_ALLOWED_USERS` to restrict access. An empty allowlist refuses to start unless `ALLOW_OPEN_ACCESS=true` is set explicitly (running open is not recommended).
- **Non-root container** -- The Docker image runs as an unprivileged `paperlessbot` user (UID 1000).
- **No secrets in code** -- All credentials are loaded from environment variables. Never commit `.env` files.
- **API token scoping** -- The bot uses a single Paperless-ngx API token. Create a dedicated user/token with appropriate permissions.
