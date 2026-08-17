# Microsoft 365 Authorization Analysis

> How the IT Copilot can (and cannot) legitimately access company Microsoft 365 data.
> Verified against current Microsoft Learn documentation (checked 2026). **No integration in
> this repo accesses real company data** — this document is the decision + approval basis that
> must come first. The app works fully on local documents without any of this.

**Non-negotiable principles:** local AI only · company-controlled data · least privilege · no
authorization bypass (no scraping, no cookie/session reuse) · traceable provenance · admin
approval treated as a design input.

---

## 0. The two things that decide everything

### (a) Delegated vs Application permissions
- **Delegated** — the app acts **as you**, the signed-in user, and can only see what *you* can
  already see. Consent may be given by you *or* an admin depending on tenant policy. This is the
  natural fit for a personal IT Copilot: it never exceeds your own access.
- **Application (app-only)** — the app runs with **no user**, and can read data **tenant-wide**
  for that permission. **Always requires admin consent**, and only a Global Administrator,
  Privileged Role Administrator, or (Cloud) Application Administrator can grant it.
  ([overview](https://learn.microsoft.com/en-us/graph/permissions-overview))

> For this project we prefer **Delegated** everywhere — it is inherently least-privilege (your
> access only) and avoids tenant-wide reach.

### (b) Can *you* even register an app?
Maybe not. Tenants commonly set **"Users can register applications = No"**, disable user consent,
and route everything through an **admin consent workflow** where you *request* and an admin
approves. Conditional Access can further gate the sign-in.
([user/admin consent](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/user-admin-consent-overview),
[configure user consent](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent))

**Therefore the app must not assume you are an admin, or even that you can register an app.**
Every Microsoft integration is **optional** and gated behind an explicit, admin-visible approval
step (see `ADMIN_SETUP.md`).

---

## 1. Authorization options (A–D)

### Option A — Delegated user authentication  ✅ recommended when Graph is allowed
```
Your M365 login → Entra ID → user/admin consent → access token (as you) → Graph → local Copilot
```
- **Flow:** OAuth 2.0 **Authorization Code + PKCE** (or device-code) via **MSAL**. Tokens cached
  locally in the OS secret store; refreshed with `offline_access`; revocable by you at any time.
- **Access:** only what your own account can see — inherently least privilege.
- **Admin consent:** needed only for the permissions that are admin-consent-only (Teams, and often
  Mail depending on the tenant's user-consent policy). OneNote/OneDrive delegated read is often
  user-consentable, but **many tenants disable user consent entirely**, so plan for admin consent.
- **Verdict:** the right model for a personal/local IT Copilot. Start here.

### Option B — Application permissions / service principal  ⚠️ avoid unless required
```
Local app → Entra app → service principal → application permissions → Graph (tenant-wide)
```
- Grants tenant-wide read (e.g. all mailboxes, all notebooks) — **excessive** for a personal tool
  and always admin-consented. Can be narrowed (Mail RBAC for Applications; `Sites.Selected` for
  SharePoint), but it is more access and more risk than a single user needs.
- **Verdict:** only if this later becomes a **shared team service** with a scoped, admin-approved
  app. Not for the MVP.

### Option C — Admin-approved internal application  ✅ the endgame for team use
```
Company Entra tenant → IT-registered app → restricted Graph permissions → local Copilot
```
- Company IT registers **one** app with the **minimum** delegated (or narrowly-scoped app)
  permissions, admin-consents them, and optionally restricts to specific mailboxes/sites. This is
  the clean, auditable path once integration is approved. `ADMIN_SETUP.md` is written for this.

### Option D — Export / controlled ingestion  ✅ always-available fallback
```
Microsoft 365 → an approved export you perform → local files → local Copilot → local RAG
```
- No Graph, no app registration. You export what you're authorized to (e.g. Outlook **PST/EML**,
  OneNote **PDF/DOCX**, SharePoint files you can already open), and drop them into the app's
  Documents uploader. **This already works today** and is the default until Graph is approved.
- **Verdict:** the guaranteed path. The connector schema is identical, so nothing is wasted when
  Graph is later enabled.

---

## 2. Per-integration analysis (verified against current docs)

Format per your request: authentication · required permissions · consent · data accessible ·
recommended scope · risks · alternative if denied.

### 📧 Outlook (Mail)
- **Authentication:** Delegated (Auth Code + PKCE).
- **Required permission (least privilege):** `Mail.Read` (delegated) — read your mail; use
  `Mail.ReadBasic` if bodies aren't needed. **Avoid** `Mail.ReadWrite` (high-impact, blocked from
  user consent under Microsoft's recommended policy).
  ([permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference))
- **Consent:** delegated `Mail.Read` is user-consentable *only if* the tenant allows user consent;
  many tenants require **admin consent**. App-only `Mail.Read` is **always** admin consent and
  reads all mailboxes (restrictable via RBAC for Applications).
- **Data accessible:** your messages + metadata (subject, sender, recipients, sent/received time,
  conversationId, folder, attachments).
- **Recommended scope:** your mailbox only; filter by folder + date range + optional sender/subject
  (see §3).
- **Risks:** email is sensitive; index only approved folders; run secret redaction before indexing.
- **Alternative if denied:** **PST/EML export** (Option D) — you export your own mailbox, no admin
  needed; threads preserved via conversationId/Thread-Index.

### 💬 Teams (channel messages & chats)
- **Authentication:** Delegated preferred; bulk export is app-only.
- **Required permissions:** `ChannelMessage.Read.All` (channel messages) and/or `Chat.Read`
  (delegated, your chats) / `Chat.Read.All` (app-only).
  ([ChannelMessage.Read.All](https://graphpermissions.merill.net/permission/ChannelMessage.Read.All))
- **Consent:** **admin consent required**, and the message/export APIs are **Protected APIs** —
  the app must be **approved by Microsoft** via a request describing intended use before it can call
  them. **Metering/payment was removed on 2025-08-25** (no billing model to configure), but the
  protection + approval + a Teams license still apply.
  ([export APIs](https://learn.microsoft.com/en-us/microsoftteams/export-teams-content),
  [payment models](https://learn.microsoft.com/en-us/graph/teams-licenses))
- **Data accessible:** team, channel, message + replies, author, timestamps, message id.
- **Recommended scope:** specific team/channel + date range only. Not "all of Teams."
- **Risks:** highest-sensitivity + strongest gating of all sources; also personal-data implications.
- **Alternative if denied:** **manual/selective capture** of the specific valuable threads (paste
  or export a conversation) into the local uploader; or an admin **eDiscovery/compliance export**.
  ⚠️ **Not all Teams content is reachable under one permission/API** — private/1:1 chats, meeting
  chats, and channel messages differ; document the gap rather than pretending parity.

### 📝 OneNote
- **Authentication:** Delegated (Auth Code + PKCE).
- **Required permission:** `Notes.Read` (delegated, your notebooks) — `Notes.Read.All` for wider or
  app-only (admin consent).
  ([Notes.Read.All](https://graphpermissions.merill.net/permission/Notes.Read.All))
- **Consent:** delegated `Notes.Read` may be user-consentable per tenant policy; app-only requires
  admin consent (Global/Privileged Role Admin).
- **Special limitation:** OneNote returns **structured HTML** per page (needs an HTML→text parser),
  Graph OneNote endpoints are **throttled/latency-sensitive**, and notebooks stored in SharePoint/
  Teams may need SharePoint permissions too. Treat OneNote as its **own** connector with its own
  parsing — do not assume parity with Mail.
- **Data accessible:** notebook, section, page, page id, created/modified, HTML content.
- **Alternative if denied:** **manual export** of a page/section to **PDF/DOCX** and upload
  (Option D).

### 📁 SharePoint / OneDrive
- **Authentication:** Delegated (your access) preferred.
- **Required permissions (least privilege):**
  - Delegated: `Files.Read` (your OneDrive) / `Sites.Read.All` reads sites you can access.
  - App-only: **`Sites.Selected`** — the least-privilege choice: an admin grants the app access to
    **specific sites only**. **Do not** combine with `Files.Read.All`/`Sites.Read.All`, which
    override `Sites.Selected` and grant tenant-wide read.
  ([Selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview),
  [restricting SharePoint access](https://practical365.com/restrict-app-access-to-sharepoint-sites/))
- **Consent:** `Sites.Selected` grant + per-site grant are admin actions.
- **Recommended:** include **only if** IT docs live there; scope to one document library/site.
- **Alternative if denied:** download the files you can already open and upload them (Option D).

---

## 3. Least-privilege permission table

| Resource | Permission | Type | Admin consent | Purpose |
|----------|------------|------|---------------|---------|
| Outlook | `Mail.Read` (or `Mail.ReadBasic`) | Delegated | Tenant-dependent (often yes) | Read approved mail (your mailbox) |
| Teams | `ChannelMessage.Read.All`, `Chat.Read` | Delegated | **Yes** (+ Protected-API approval) | Read approved channel/chat messages |
| OneNote | `Notes.Read` | Delegated | Tenant-dependent | Read approved notebooks (yours) |
| SharePoint | `Sites.Selected` (app) / `Sites.Read.All` (deleg.) | App / Delegated | **Yes** | Read approved site/library |
| OneDrive | `Files.Read` | Delegated | Tenant-dependent | Read approved OneDrive files |
| (baseline) | `User.Read`, `offline_access` | Delegated | No | Sign in + refresh token |

All read-only. No write, no `.ReadWrite`, no `Directory.*`, no broad `*.Read.All` unless an admin
deliberately chooses app-only.

---

## 4. What you can do yourself vs what needs an admin

| Step | You (standard user) | Needs M365 / Entra admin |
|------|---------------------|--------------------------|
| Register the Entra app | Only if "Users can register applications = Yes" | If disabled → **admin registers it** |
| Consent to delegated read | Only if user consent is enabled | If disabled → **admin consent** (or admin-consent workflow request) |
| Consent to application permissions | Never | **Always admin** |
| Approve Teams Protected-API usage | No | **Admin submits Microsoft request** |
| Grant `Sites.Selected` to a site | No | **Admin** |
| Use export fallback (Option D) | **Yes** | No |

Where a step needs an admin, the app surfaces it verbatim as an **ACTION REQUIRED FROM M365 ADMIN**
block (see `ADMIN_SETUP.md` and the in-app **Integrations & Security** page).

---

## 5. Recommended strategy

1. **Now:** ship and use the app on **local documents + Option D exports**. Zero authorization
   needed; fully functional. *(This is the current state of the repo.)*
2. **When you want live sync:** pursue **Option A (delegated), least privilege, one source at a
   time**, starting with **Outlook `Mail.Read`** or **OneNote `Notes.Read`** (lowest friction).
   Hand IT the generated `ADMIN_SETUP.md` request.
3. **Teams last** — it has the strongest gating (Protected API + admin consent). Until approved,
   use manual/selective capture.
4. **Only move to Option B/C (app-only)** if this becomes a **shared team service**, and even then
   scope hard (`Sites.Selected`, Mail RBAC for Applications).

## 6. Fallback if Microsoft 365 integration is denied

The app is **fully usable with no Graph access at all**: upload PDFs/DOCX/XLSX/TXT/MD/CSV exported
from Outlook (PST/EML→files), OneNote (→PDF/DOCX), SharePoint (download), and Teams (selective
capture). Same RAG, same citations, same provenance schema. Microsoft 365 connectors are an
**optional enhancement**, never a dependency.

> If any required permission/consent/registration is blocked, the app **stops and explains the exact
> limitation and the legitimate path** — it never attempts a workaround.
