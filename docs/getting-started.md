# Getting started

## Before you start

You need three values. Get them once and keep them out of git.

1. A bot token. Open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, choose a name and a username ending in `bot`. BotFather answers with the token.
2. A Paperless API token. In Paperless-ngx click your user name (top right), then My Profile; the API Auth Token section has a button that creates one. Without the web UI: `curl -X POST http://your-paperless:8000/api/token/ -d username=... -d password=...` returns it.
3. Your Telegram user id. Send `/start` to [@userinfobot](https://t.me/userinfobot); it answers with the number. For several people, separate the ids with commas.

`PAPERLESS_URL` is the address the bot can reach, which is not always the address you type in a browser. Use the host's LAN address and port when the bot runs in its own container, or the Paperless container's name (`http://paperless:8000`) when both are on the same Docker network. `PAPERLESS_PUBLIC_URL` is the browser address, used for the Open in Paperless links; it falls back to `PAPERLESS_URL`.

Works with Paperless-ngx 2.x and 3.x.

## Docker

```bash
docker run -d \
  --name paperless-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_bot_token \
  -e PAPERLESS_URL=http://paperless.home:8000 \
  -e PAPERLESS_TOKEN=your_paperless_api_token \
  -e TELEGRAM_ALLOWED_USERS=123456789 \
  drumsergio/paperless-telegram-bot:v0.7.0
```

## Docker Compose

Put this next to a `.env` file holding `TELEGRAM_BOT_TOKEN`, `PAPERLESS_TOKEN` and `TELEGRAM_ALLOWED_USERS` (start from [`.env.example`](https://github.com/GeiserX/paperless-telegram-bot/blob/main/.env.example)), then run `docker compose up -d`. `PAPERLESS_URL` here assumes Paperless runs as a service named `paperless` on the same Compose network; otherwise use the host's LAN address.

```yaml
services:
  paperless-telegram-bot:
    image: drumsergio/paperless-telegram-bot:v0.7.0
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

## From source

Python 3.11 or newer. The 0.7.0 package on PyPI is missing the bot's modules and stops with `ModuleNotFoundError: No module named 'paperless_bot.api'`, so install from a clone until the next release.

```bash
git clone https://github.com/GeiserX/paperless-telegram-bot.git
cd paperless-telegram-bot
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill in the four values
paperless-bot run
```

With this install the bot reads the `.env` in the clone's folder, whatever directory you start it from. `paperless-bot --version` prints the installed version.

## What a working start looks like

The log, in this order (the timestamps and logger names are left out):

```
Paperless Telegram Bot v0.7.0 starting...
Connected to Paperless-NGX <version> (API v<n>) at http://paperless:8000
Health check endpoint running on port 8080
Telegram bot configured
Starting Telegram bot polling...
Bot commands registered with Telegram
```

Then open your bot in Telegram and send `/start`. The reply says to send a document or photo to upload it and any text to search, and lists the commands. In Docker, `docker inspect --format '{{.State.Health.Status}}' paperless-telegram-bot` prints `healthy` after the first health check. If the container stops right after starting, the log names the missing variable; see [Troubleshooting](troubleshooting.md).

Next: [Usage](usage.md), then [Configuration](configuration.md) for the optional settings.
