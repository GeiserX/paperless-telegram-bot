<p align="center">
  <img src="https://raw.githubusercontent.com/GeiserX/paperless-telegram-bot/main/docs/images/banner.svg" alt="paperless-telegram-bot" width="900"/>
</p>

<p align="center">
  <strong>Manage Paperless-NGX documents entirely through Telegram.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/paperless-telegram-bot/"><img src="https://img.shields.io/pypi/v/paperless-telegram-bot?style=flat-square&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/GeiserX/paperless-telegram-bot/tests.yml?style=flat-square&logo=github&label=tests" alt="Tests"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/GeiserX/paperless-telegram-bot?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/drumsergio/paperless-telegram-bot"><img src="https://img.shields.io/docker/pulls/drumsergio/paperless-telegram-bot?style=flat-square&logo=docker" alt="Docker Pulls"></a>
  <a href="https://codecov.io/gh/GeiserX/paperless-telegram-bot"><img src="https://codecov.io/gh/GeiserX/paperless-telegram-bot/graph/badge.svg" alt="codecov"></a>
</p>

---

A Telegram bot for [Paperless-NGX](https://docs.paperless-ngx.com/), run in Docker or from PyPI. Upload documents and photos, search the archive, set tags, correspondents and document types, review the inbox and download files, all from a Telegram chat.

## Features

- **Document Upload** -- send any file or photo and it goes to Paperless-NGX; duplicates are detected and linked.
- **Full-Text Search** -- `/search` with paginated results and inline keyboard navigation.
- **Metadata Management** -- assign tags, correspondents, and document types through inline keyboards.
- **Inbox Review** -- `/inbox` lists documents with your inbox tag; mark them reviewed with one tap.
- **Document Download** -- original files straight to Telegram (up to 50 MB).
- **Recent Documents and Statistics** -- `/recent` and `/stats`.
- **User Authorization** -- only the Telegram user IDs in the allowlist can use the bot.
- **Health Endpoint and Non-Root Docker** -- `/health` for Docker health checks; runs as an unprivileged user.

## Quick start

```bash
docker run -d --name paperless-telegram-bot --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_bot_token -e PAPERLESS_URL=http://your-paperless:8000 \
  -e PAPERLESS_TOKEN=your_api_token -e TELEGRAM_ALLOWED_USERS=123456789 drumsergio/paperless-telegram-bot:v0.7.0
```

Works with Paperless-NGX 2.x and 3.x. Docker Compose and a manual install are in [Getting started](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/getting-started.md).

## Documentation

- [Getting started](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/getting-started.md): Docker, Docker Compose, manual
- [Configuration](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/configuration.md): every environment variable, and security notes
- [Usage](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/usage.md): commands, uploads and the metadata flow
- [How it works](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/how-it-works.md): code layout and design decisions
- [Troubleshooting](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/troubleshooting.md)
- [Development](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/development.md): tests, linting, contributing, related projects
- [Roadmap](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/ROADMAP.md)

## License

[GPL-3.0-or-later](https://github.com/GeiserX/paperless-telegram-bot/blob/main/LICENSE)
