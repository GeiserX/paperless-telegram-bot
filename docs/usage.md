# Usage

Open your bot in Telegram. Everything below happens in that one chat. `/start` answers with what to do: send a document or photo to upload it, send any text to search, and the list of commands.

## Upload

Send a file or a photo. The bot uploads it to Paperless-ngx, waits for Paperless to process it, and then shows the document's title with four buttons: Set Tags, Set Correspondent, Set Document Type and Done. A file sent as a document keeps its file name, which Paperless uses as the title; a photo is named after the time it was sent. Files over 20 MB are refused with a message, because Telegram does not let bots download anything larger; add those through the Paperless web UI or its consume folder.

If Paperless already has the same file, the bot says which document it is and offers it for download instead of storing it twice.

## Tags, correspondent and document type

Set Tags opens a paged list with a box per tag; tap to tick or untick, then Confirm Tags. Set Correspondent and Set Document Type open a single-choice list each, with Skip. Every list has a + New button that asks for a name in the chat and creates the item in Paperless. Done finishes and, unless `REMOVE_INBOX_ON_DONE=false`, removes the inbox tag; the reply links the document in Paperless.

## Search

Send any text. The bot runs a full-text search and answers with a page of results: title, correspondent, type, tags, date added and a snippet of the text, with a Download button each and Prev and Next when there are more pages. `/search <query>` does the same. `MAX_SEARCH_RESULTS` sets the page size (10 by default).

## Download

Tap Download on any result. The original file arrives in the chat, up to 50 MB (Telegram's limit for a bot upload); larger files get a message saying so.

## Inbox

`/inbox` lists the documents that still carry the inbox tag (the tag Paperless marks as inbox, or `INBOX_TAG`), each with Download and Reviewed. Reviewed removes the tag. `/recent` lists the latest documents the same way, without the Reviewed button.

## Commands

| Command | What it does |
|---------|--------------|
| `/search <query>` | Full-text search; plain text does the same |
| `/recent` | The latest documents, with Download buttons |
| `/inbox` | Documents with the inbox tag, with Download and Reviewed buttons |
| `/stats` | Document, inbox, correspondent, tag and document type counts |
| `/help` | The same message as `/start` |
