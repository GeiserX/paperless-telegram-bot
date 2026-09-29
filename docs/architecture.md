# Architecture

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
