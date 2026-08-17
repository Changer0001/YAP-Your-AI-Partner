# Connectors

Modular sources feed the same ingestion pipeline. **Authorization is separate from ingestion**: a
connector must report itself *available/authorized* before it can fetch, and an auth failure
surfaces a clear, specific permission message — never "something went wrong."

```
connectors/
├── base.py            ConnectorInfo + BaseConnector (status/authorize/fetch/normalize)
├── registry.py        lists connectors and their live status
├── local/
│   └── documents.py   local files + import folder  → AVAILABLE now
└── microsoft/
    └── __init__.py    Outlook · Teams · OneNote · SharePoint · OneDrive
                       metadata + required permissions + status only (NOT configured)
```

## Status model
Each connector reports one of:
- `available` — usable now (local documents / import folder).
- `not_configured` — supported in principle, needs setup/approval (all Microsoft connectors today).
- `blocked` — an authorization/consent requirement is not met; the UI shows the exact permission and
  the **ACTION REQUIRED FROM M365 ADMIN** text (from `ADMIN_SETUP.md`).

## Microsoft connectors — current stance
Per `MICROSOFT_365_AUTHORIZATION.md`, corporate access is unlikely to be granted to local IT, so
Microsoft connectors ship as **metadata + status only** (no live calls). The **supported path is
export** (`EXPORT_GUIDE.md`): a human exports M365 data to files → the **local/import** connector
ingests them. If delegated Graph is ever approved, a real connector drops into `microsoft/` behind
the same `BaseConnector` interface, preserving the provenance schema (§ Data Provenance).

## Adding a connector
1. Subclass `BaseConnector`; declare `ConnectorInfo` (name, required permissions, consent, scope).
2. Implement `status()`, `authorize()`, `fetch(scope)`, `normalize()` → provenance records.
3. Register it; it appears on the **Integrations & Security** page with its real status.
No connector auto-ingests: fetching is always user-initiated and scope-limited.
