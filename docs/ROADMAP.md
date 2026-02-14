# Roadmap

Planned features and improvements for the Paperless Telegram Bot, roughly ordered by priority.

## High Priority

### New Document Notifications

Push a Telegram message when Paperless finishes processing a new document. Can be implemented as a background polling loop (check `/api/documents/?ordering=-added` every N minutes) or via Paperless webhooks (v2.x+). This is the single most requested feature in the Paperless community for Telegram integration.

**Env vars:**
- `NOTIFY_NEW_DOCUMENTS` (default: `false`)
- `NOTIFY_POLL_INTERVAL` (default: `300` seconds)

### Document Thumbnail Preview

When listing documents (inbox, search, recent), send the thumbnail image alongside the text. Paperless exposes `/api/documents/{id}/thumb/`. Makes mobile usage much more visual and useful.

### Creation Date Editing

The bot supports tags, correspondent, and document type, but not the document date. Many users need to correct the auto-detected date. Add a "Set Date" button to the metadata keyboard with common formats (today, yesterday, pick a date).

### Document Notes

Paperless supports notes on documents (added in v1.14). Users use notes for audit trails, processing remarks, etc. Add "Add Note" to the metadata flow.

## Medium Priority

### Custom Fields

Paperless v2.x added custom fields (text, number, date, boolean, URL, monetary). Power users rely on these heavily for structured data. Would need dynamic keyboard generation based on field types.

### Consumption Templates

When uploading via the bot, let users optionally select a consumption template that pre-fills metadata. Useful for recurring document types (monthly invoices from same vendor).

### Storage Paths

Some users organize physical storage and use Paperless storage paths to track where documents are filed. Add "Set Storage Path" to metadata.

### Bulk Operations from Inbox

Select multiple documents and apply the same tag/correspondent/type to all at once. Current flow is one-at-a-time.

### Cloud Storage Import

Automatic document pickup from cloud storage providers:

**Google Drive / Google Docs:**
- No native Paperless integration exists
- Best current approach: `GoogleDrivePaperlessImporter` (C#, [GitHub](https://github.com/ViMaSter/GoogleDrivePaperlessImporter)) -- scans a Drive folder and uploads via Paperless API
- Alternative: n8n workflow with Google Drive + HTTP Request nodes
- Workaround: `rclone sync` (periodic cron) from Google Drive to local consume folder
- Note: `rclone mount` (FUSE) is problematic and not recommended -- consume folder stops detecting files

**Microsoft OneDrive / SharePoint / Office 365:**
- No native Paperless integration exists
- Best current approach: n8n workflow with OneDrive/SharePoint nodes
- Workaround: OneDrive client sync to local folder + consume directory (timing issues with file access during sync)
- Alternative: `rclone sync` (periodic cron) from OneDrive to local consume folder
- Same `rclone mount` caveat applies

**General pattern:** The most reliable approach for any cloud storage is: cloud API or sync client writes to a local directory, Paperless-NGX watches that directory as a consume folder. Direct API-to-API (cloud -> Paperless REST API) avoids filesystem issues entirely but requires custom scripting or n8n.

## Lower Priority

### Multi-User Token Support

Map different Telegram user IDs to different Paperless API tokens. Currently one token for all bot users. Would allow per-user permissions and document visibility.

### ASN (Archive Serial Number)

Physical document tracking. Niche but some users swear by it for managing paper archives.

### Saved View Access

Let users access their Paperless saved views from Telegram (e.g., `/view Inbox`, `/view Hotmail`). Would query the saved view's filter rules and display matching documents.
