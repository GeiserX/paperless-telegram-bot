# Troubleshooting

## The container stops right after it starts

Cause: a setting is missing, and the log names it.

- `Required environment variable 'PAPERLESS_TOKEN' is not set.` The required ones are `TELEGRAM_BOT_TOKEN`, `PAPERLESS_URL` and `PAPERLESS_TOKEN`.
- `TELEGRAM_ALLOWED_USERS is empty.` The bot refuses to start without an allowlist.

Fix: set the variable. For the allowlist, put your Telegram user id in `TELEGRAM_ALLOWED_USERS` (send `/start` to [@userinfobot](https://t.me/userinfobot) to find it). `ALLOW_OPEN_ACCESS=true` runs the bot open to every Telegram user; it can then upload into, search and download from your archive, so use it only on purpose.

## The bot replies "You are not authorized to use this bot"

Cause: your Telegram user id is not in `TELEGRAM_ALLOWED_USERS`.

Fix: add it (comma-separated for several people) and recreate the container.

## An upload says "Processing timed out"

Cause: Paperless did not finish the document within `UPLOAD_TASK_TIMEOUT` seconds (300 by default), for example because its workers are busy. The document often appears in Paperless a little later.

Fix: check Paperless for the document. If this happens often, raise `UPLOAD_TASK_TIMEOUT`.

## The container is unhealthy

Cause: `/health` on `HEALTH_PORT` (8080) asks Paperless for one document with your token and answers 503 when that fails. The JSON body says why, for example `"paperless": "unreachable: ConnectError"`.

Fix: check that `PAPERLESS_URL` is reachable from the container and that `PAPERLESS_TOKEN` is valid (`docker inspect --format '{{json .State.Health}}' paperless-telegram-bot` shows the last health check).

## Reporting a bug

Open an [issue](https://github.com/GeiserX/paperless-telegram-bot/issues) with:

- the version you run (the `version` field of `/health`, or the image tag);
- your Paperless-NGX version;
- the log around the problem, with `LOG_LEVEL=DEBUG` if you can reproduce it;
- what you sent to the bot and what it answered.

Leave out tokens and document contents.
