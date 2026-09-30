<p align="center">
  <img src="https://raw.githubusercontent.com/GeiserX/paperless-telegram-bot/main/docs/images/banner.svg" alt="paperless-telegram-bot banner" width="900"/>
</p>

<p align="center">
  <strong>Your Paperless-ngx archive, run from Telegram.</strong>
</p>

<p align="center">
  <a href="https://github.com/GeiserX/paperless-telegram-bot/releases"><img src="https://img.shields.io/github/v/release/GeiserX/paperless-telegram-bot?style=flat-square" alt="Release"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/GeiserX/paperless-telegram-bot/tests.yml?style=flat-square&logo=github&label=tests" alt="Tests"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/GeiserX/paperless-telegram-bot?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/drumsergio/paperless-telegram-bot"><img src="https://img.shields.io/docker/pulls/drumsergio/paperless-telegram-bot?style=flat-square&logo=docker" alt="Docker pulls"></a>
  <a href="https://github.com/GeiserX/paperless-telegram-bot/stargazers"><img src="https://img.shields.io/github/stars/GeiserX/paperless-telegram-bot?style=flat-square" alt="GitHub stars"></a>
</p>

---

paperless-telegram-bot is a Telegram bot for [Paperless-ngx](https://docs.paperless-ngx.com/), run in Docker. Send a photo or a file from your phone and it lands in your archive; then tag it, file it, search it and get it back, all from the chat. The bot polls Telegram and talks to Paperless over its API, so it needs no public URL, no open port and no VPN on the phone, and Paperless can stay on your LAN.

## Features

- Send a photo or any file up to 20 MB (Telegram's limit for bots) and it is uploaded to Paperless; the reply changes to the document's title once Paperless has finished processing it.
- Tag it, pick the correspondent and the document type from inline keyboards right after the upload, or create a new tag, correspondent or type without leaving the chat.
- A file Paperless already has is not stored twice: the bot names the existing document and offers it for download.
- Type any text to search the archive; results come in pages, each with a Download button. `/search` does the same.
- `/inbox` lists what still carries the inbox tag; Reviewed clears it with one tap, and so does Done after an upload.
- Get the original file back in the chat, up to 50 MB.
- `/recent` shows the latest documents and `/stats` the archive's counts.
- Only the Telegram user ids you list can use the bot; everyone else is refused. It refuses to start with an empty list unless you set `ALLOW_OPEN_ACCESS=true`, which opens it to every Telegram user.
- Works with Paperless-ngx 2.x and 3.x.

## Quick start

```bash
docker run -d --name paperless-telegram-bot --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_bot_token \
  -e PAPERLESS_URL=http://paperless.home:8000 \
  -e PAPERLESS_TOKEN=your_paperless_api_token \
  -e TELEGRAM_ALLOWED_USERS=123456789 \
  drumsergio/paperless-telegram-bot:v0.7.0
```

The image is amd64 only; on arm64, install from source as [Getting started](https://geiserx.github.io/paperless-telegram-bot/getting-started/#from-source) shows.

Get the three values first: the bot token from [@BotFather](https://t.me/BotFather) (`/newbot`), the Paperless API token from your Paperless profile (click your user name, then My Profile, API Auth Token), and your own Telegram user id from [@userinfobot](https://t.me/userinfobot). `PAPERLESS_URL` is the address the bot can reach, which is not always the one in your browser. Use the host's LAN address, or the Paperless container's name when both share a Docker network. When it works the log ends with `Bot commands registered with Telegram`, and sending `/start` to your bot in Telegram gets the command list back; Docker Compose, a run from source and what a working start looks like are in [Getting started](https://geiserx.github.io/paperless-telegram-bot/getting-started/).

## Documentation

Everything below is on the site, https://geiserx.github.io/paperless-telegram-bot/.

- [Getting started](https://geiserx.github.io/paperless-telegram-bot/getting-started/): what you need first, Docker, Docker Compose, from source, and what a working start looks like
- [Configuration](https://geiserx.github.io/paperless-telegram-bot/configuration/): every environment variable and its default, and the security notes
- [Usage](https://geiserx.github.io/paperless-telegram-bot/usage/): a session step by step: upload, tags, search, download, inbox
- [How it works](https://geiserx.github.io/paperless-telegram-bot/how-it-works/): the code layout and the design decisions
- [Troubleshooting](https://geiserx.github.io/paperless-telegram-bot/troubleshooting/): symptom, cause, fix
- [Development](https://geiserx.github.io/paperless-telegram-bot/development/): tests, linting, contributing
- [Related projects](https://geiserx.github.io/paperless-telegram-bot/related/): the other Telegram bots and tools
- [Roadmap](https://github.com/GeiserX/paperless-telegram-bot/blob/main/docs/ROADMAP.md)

## License

[GPL-3.0-or-later](https://github.com/GeiserX/paperless-telegram-bot/blob/main/LICENSE)
