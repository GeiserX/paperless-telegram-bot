# Development

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

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`feat/my-feature` or `fix/my-bug`)
3. Follow the existing code style (enforced by `ruff`)
4. Add tests for new functionality
5. Submit a pull request

This project follows [Conventional Commits](https://conventionalcommits.org) and [Semantic Versioning](https://semver.org).

## Related projects

| Project | Description |
|---------|-------------|
| [Telegram-Archive](https://github.com/GeiserX/Telegram-Archive) | Automated, incremental Telegram backups with a local web viewer |
| [telegram-delay-channel-cloner](https://github.com/GeiserX/telegram-delay-channel-cloner) | Telegram bot that relays messages between channels with configurable delay |
| [telegram-slskd-local-bot](https://github.com/GeiserX/telegram-slskd-local-bot) | Automated music discovery and download via Telegram bot with Soulseek |
| [AskePub](https://github.com/GeiserX/AskePub) | Telegram bot for ePub annotation with GPT-4 |
| [jellyfin-telegram-channel-sync](https://github.com/GeiserX/jellyfin-telegram-channel-sync) | Sync Jellyfin access with Telegram channel membership |
| [telegram-archive-mcp](https://github.com/GeiserX/telegram-archive-mcp) | MCP Server for Telegram-Archive |
| [n8n-nodes-telegram-archive](https://github.com/GeiserX/n8n-nodes-telegram-archive) | n8n community node for Telegram-Archive |
