# Admin Setup — for the Company Microsoft 365 / Entra Administrator

> This page is written **for a Microsoft 365 / Entra ID administrator**. An employee wants to use a
> **local, private IT Copilot** that answers questions from IT documentation. They are requesting
> **read-only** access to specific Microsoft 365 data, on a **least-privilege, delegated** basis.
> Nothing is auto-ingested and no data is sent to any external AI service — the AI model
> (Qwen 2.5 3B) runs locally on the employee's machine.

## What the application is
- A local FastAPI + local LLM app on the employee's computer. All processing, storage, and
  inference are **on-device**. See `DATA_SECURITY.md`.
- It uses Microsoft **Graph** only through officially supported, read-only permissions, using
  **delegated** auth (the app acts as the signed-in user and can only see what that user can
  already see). It never scrapes, never reuses cookies/session tokens, and never bypasses consent
  or Conditional Access.

## What you're being asked to configure (start with ONE source)

### 1. App registration (Microsoft Entra ID)
If **"Users can register applications" = No**, the employee cannot create the app — **you register
it**:
- Entra admin center → **App registrations → New registration**.
- Name: `Local IT Copilot (<employee>)`. Single tenant. Redirect URI (Public client/native):
  `http://localhost` (Auth Code + PKCE) — or enable **device code flow**.
- Note the **Application (client) ID** and **Directory (tenant) ID** and give them to the employee.
  No client secret is needed for delegated public-client flows.

### 2. API permissions — grant only what's requested
Add **Microsoft Graph → Delegated** permissions, least privilege, read-only:

| Start with | Permission | Why | Admin consent |
|------------|------------|-----|---------------|
| Baseline | `User.Read`, `offline_access` | sign-in + token refresh | No |
| Outlook | `Mail.Read` | read the employee's mail | Often (tenant policy) |
| OneNote | `Notes.Read` | read the employee's notebooks | Tenant policy |
| SharePoint/OneDrive | `Sites.Selected` (or delegated `Files.Read`) | scoped site/file read | Yes (`Sites.Selected`) |
| Teams (later) | `ChannelMessage.Read.All`, `Chat.Read` | read approved messages | **Yes + Protected-API approval** |

- Grant **admin consent** for the ones the tenant requires (or approve the employee's request via
  the **admin consent workflow**).
- **Do not** add `*.ReadWrite`, `Files.Read.All`/`Sites.Read.All` (tenant-wide), or `Directory.*`.
  For SharePoint prefer **`Sites.Selected`** and grant the app only the **specific site(s)** needed
  (this is deliberately least-privilege — do not also add `Files.Read.All`, which would override it).

### 3. Teams (only if/when requested) — extra step
`ChannelMessage.Read.All` / the Teams **Export APIs** are **Protected APIs**: you must submit
Microsoft's **request for protected API access** describing the intended use before the app can
call them. (As of 2025-08-25 there is **no payment/metering** to configure; a Teams license is
required.) Approve the specific team/channel scope only.

## How to restrict access
- Prefer **delegated** (employee's own access only).
- For app-only mail, use **RBAC for Applications / Application Access Policy** to limit to specific
  mailboxes.
- For SharePoint, use **`Sites.Selected`** + per-site grant.
- Apply **Conditional Access** as normal; the app supports interactive sign-in and MFA.

## How to revoke access (any time)
- **Enterprise applications → the app → Permissions → Revoke admin consent**, and/or
  **Delete** the app registration / disable the service principal. The employee can also remove the
  app from **My Account → App permissions**. Cached tokens expire and cannot be refreshed.

## What data the app reads vs keeps local
- **Reads (read-only):** only the scoped items above (approved mail folder / notebook / site).
- **Stays local:** all downloaded content, the vector index, and the LLM. **Nothing is sent to any
  external AI service.** See `DATA_SECURITY.md` for exactly what is stored and how to delete it.

## Security controls to consider
- Keep it **delegated + read-only + least privilege**; approve **one source at a time**.
- Require the employee's device to meet your endpoint/compliance policy (the data lands there).
- Audit consents periodically (Enterprise apps → Permissions); revoke if the employee changes role.

---

### Copy-paste request block (employee → admin)
```
ACTION REQUIRED FROM M365 / ENTRA ADMIN
App: Local IT Copilot (read-only, delegated, on-device AI)
Register app: yes/no (if user registration disabled)
Graph permissions (delegated, read-only):
  - User.Read, offline_access
  - <Mail.Read | Notes.Read | Sites.Selected | Files.Read | ChannelMessage.Read.All+Chat.Read>
Admin consent required: <per table above>
Teams only: submit Protected-API access request; Teams license required
Scope: <specific mailbox folder / notebook / site / team+channel + date range>
Reason: read approved IT documentation into a local, private knowledge assistant
Data leaves tenant to external AI: NO (Qwen 2.5 3B runs locally)
Revoke: revoke admin consent / delete app registration
```
