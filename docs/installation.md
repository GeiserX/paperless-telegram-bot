# Installation

## Docker (Recommended)

```bash
docker run -d \
  --name paperless-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_bot_token \
  -e PAPERLESS_URL=http://your-paperless:8000 \
  -e PAPERLESS_TOKEN=your_api_token \
  -e TELEGRAM_ALLOWED_USERS=123456789 \
  drumsergio/paperless-telegram-bot:v0.7.0
```

## Docker Compose

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

## Manual Installation

Requires Python 3.11 or newer.

```bash
git clone https://github.com/GeiserX/paperless-telegram-bot.git
cd paperless-telegram-bot
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # Edit with your values
python -m paperless_bot run
```

Next: [Configuration](configuration.md).
