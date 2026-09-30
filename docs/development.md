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
