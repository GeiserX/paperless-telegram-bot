# Usage

## Commands

| Command | Description |
|---------|-------------|
| `/search <query>` | Full-text search across all documents |
| `/recent` | Show recently added documents |
| `/inbox` | List documents in the inbox with review actions |
| `/stats` | Display Paperless-NGX statistics |
| `/help` | Show available commands and usage |

In addition to commands, you can send any **file or photo** directly to the bot to upload it to Paperless-NGX. After upload, an interactive keyboard lets you assign tags, a correspondent, and a document type.

## Features in detail

- **Document Upload** -- Send any file or photo to the bot and it gets uploaded to Paperless-NGX automatically. Duplicates are detected and linked.
- **Full-Text Search** -- Search across all your documents with `/search`. Results are paginated with inline keyboard navigation.
- **Metadata Management** -- After uploading (or on any document), assign tags, correspondents, and document types through interactive inline keyboards.
- **Inbox Review** -- `/inbox` lists all documents tagged with your inbox tag. Mark them as reviewed with a single tap.
- **Document Download** -- Download original files directly to Telegram (up to 50 MB).
- **Recent Documents** -- `/recent` shows the latest documents added to your archive.
- **System Statistics** -- `/stats` displays document counts, tag usage, and storage information.
- **Health Endpoint** -- Built-in `/health` HTTP endpoint for Docker health checks and monitoring.
- **User Authorization** -- Restrict bot access to specific Telegram user IDs via allowlist.
- **Non-Root Docker** -- Runs as an unprivileged user inside the container.
