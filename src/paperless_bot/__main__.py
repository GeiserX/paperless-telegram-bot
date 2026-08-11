"""
Entry point for Paperless Telegram Bot.
Can be run as: python -m paperless_bot
"""

import argparse
import asyncio
import logging
import sys
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from paperless_bot import __version__
from paperless_bot.api.client import PaperlessClient
from paperless_bot.bot.handlers import create_bot
from paperless_bot.config import Config, setup_logging

logger = logging.getLogger(__name__)


def create_health_app(config: Config) -> FastAPI:
    """Create a FastAPI app whose /health reflects Paperless connectivity.

    Returning 200 unconditionally would keep the Docker healthcheck green
    while every user command fails; instead the endpoint performs a cheap
    authenticated request against Paperless and reports 503 when it fails.
    """
    app = FastAPI(title="Paperless Telegram Bot", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health():
        checks = {"bot": "ok"}
        healthy = True
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{config.paperless_url.rstrip('/')}/api/documents/",
                    params={"page_size": 1},
                    headers={"Authorization": f"Token {config.paperless_token}"},
                )
                resp.raise_for_status()
            checks["paperless"] = "ok"
        except Exception as exc:  # noqa: BLE001 — any failure means degraded
            checks["paperless"] = f"unreachable: {type(exc).__name__}"
            healthy = False

        return JSONResponse(
            {"status": "ok" if healthy else "degraded", "version": __version__, "checks": checks},
            status_code=200 if healthy else 503,
        )

    return app


def run_health_server(config: Config):
    """Run the health check HTTP server in a background thread."""
    app = create_health_app(config)
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.health_port, log_level="warning")
    server = uvicorn.Server(uv_config)
    server.run()


def validate_paperless_connection(config: Config, attempts: int = 3, retry_delay: float = 5.0) -> bool:
    """Probe Paperless at startup so misconfiguration fails fast and loud.

    Retries a few times before giving up, so a Paperless that is a moment
    behind the bot (e.g. both restarting after a deploy) does not force an
    immediate container exit.
    """

    async def _probe():
        client = PaperlessClient(config.paperless_url, config.paperless_token)
        try:
            return await client.probe()
        finally:
            await client.close()

    info = None
    for attempt in range(1, attempts + 1):
        try:
            info = asyncio.run(_probe())
            break
        except Exception as exc:
            logger.error(
                "Cannot talk to Paperless-NGX at %s (attempt %d/%d): %s",
                config.paperless_url,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                time.sleep(retry_delay)
    if info is None:
        logger.error("Check PAPERLESS_URL and PAPERLESS_TOKEN before restarting.")
        return False

    logger.info(
        "Connected to Paperless-NGX %s (API v%s) at %s",
        info["server_version"],
        info["api_version"],
        config.paperless_url,
    )
    return True


def cmd_run(args):
    """Run the Telegram bot with health check endpoint."""
    config = Config()
    setup_logging(config)

    logger.info(f"Paperless Telegram Bot v{__version__} starting...")

    if not validate_paperless_connection(config):
        sys.exit(1)

    # Start health check server in background
    health_thread = threading.Thread(target=run_health_server, args=(config,), daemon=True)
    health_thread.start()
    logger.info(f"Health check endpoint running on port {config.health_port}")

    # Start the Telegram bot (blocking)
    bot_app = create_bot(config)
    logger.info("Starting Telegram bot polling...")
    bot_app.run_polling(drop_pending_updates=config.drop_pending_updates)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="paperless-bot",
        description="Manage Paperless-NGX documents via Telegram.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'run' command (default)
    subparsers.add_parser("run", help="Start the bot and health server")

    args = parser.parse_args()

    if args.command is None:
        # Default to 'run'
        args.command = "run"

    if args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
