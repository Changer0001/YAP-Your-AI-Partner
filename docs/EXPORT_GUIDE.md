# Export / Ingestion Guide — using M365 data *without* API access

> The realistic path when corporate (Hyatt) will **not** grant Graph/API permissions to local IT.
> Everything here uses access you **already have as an authorized user**, through Microsoft's own
> supported export/save features — no API, no admin, no scraping.

## The line we do not cross
❌ **No** automated web scraping of corporate pages, **no** cookie/session-token reuse, **no**
browser automation logging in as you, **no** unauthorized bulk pulls. Being able to *view* a page
in your browser does not authorize a program to harvest it; that violates acceptable-use policy and
trips security monitoring.

✅ **Yes** to *you* exporting/saving data you're authorized to see, using built-in features, then
feeding the resulting **files** to the local Copilot. This is legitimate and fully supported.

> Rule of thumb: if **a human clicks "Export/Save/Print/Download/Sync"**, it's fine. If **a script
> logs in and harvests**, it's not.

## How to get each source out as files

### 📧 Outlook email
- **Export mailbox/folder:** Outlook (desktop) → **File → Open & Export → Import/Export → Export to
  a file → Outlook Data File (.pst)**. Pick the folder(s), export. (Preserves threads via
  ConversationId.) *No admin needed.*
- **Single emails:** select → **Save As** `.msg`, or **Print → Save as PDF**.
- Then: convert/drop the resulting **PDF/DOCX/MSG-as-text** into the import folder (PST parsing is a
  Phase-2 feature; for now export the specific emails to PDF).

### 📝 OneNote
- **Export a page/section/notebook:** OneNote (desktop) → **File → Export → PDF or Word (.docx)**.
- Or **Print → Save as PDF** per page.
- Drop the PDFs/DOCX into the import folder. *No admin needed.*

### 📁 Knowledge base / SharePoint / OneDrive
- **If it's SharePoint/OneDrive:** use the **OneDrive/SharePoint Sync** button (a Microsoft feature)
  to sync the library to a local folder, then point the importer at it. This is sanctioned sync, not
  scraping.
- **Otherwise:** **Download** the documents you can open, or **Print → Save as PDF** per wiki page.

### 💬 Teams
- **Selective capture:** for the genuinely valuable threads ("we fixed X by changing Y"), copy the
  conversation into a text/markdown note, or **Print → Save as PDF**, and drop it in.
- Bulk Teams export needs admin (eDiscovery/compliance) — out of scope for local IT.

## Make it low-effort: the bulk import folder
You don't have to upload files one at a time. There is a watched **import folder**:

```
data/import/
```
1. Save/export everything above into that folder (subfolders are fine).
2. In the app: **Documents → Import from folder** (or `POST /api/documents/import`).
3. The app scans the folder, **skips anything already indexed** (by content hash), and indexes the
   rest with provenance. Re-run any time you add more exports.

Supported now: **PDF, DOCX, XLSX, TXT, MD, CSV**. So export from M365 to those formats and you're
done — the assistant can then answer from that content with citations, entirely locally.

## Provenance is preserved
Each imported file keeps `source_type=local_document`, filename, page/section, size, and the dates
+ metadata you set (site, version, author…), so answers can still cite exactly where they came from
and reason about current-vs-historical — see `RAG.md`.
