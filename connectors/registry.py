"""Live status of all connectors, for the Integrations & Security page.

Microsoft connectors report NOT_CONFIGURED with their exact least-privilege permissions and a clear
ACTION REQUIRED block — never a vague error. Values mirror docs/MICROSOFT_365_AUTHORIZATION.md.
"""
from connectors.base import (AVAILABLE, NOT_CONFIGURED, ConnectorInfo)


def _microsoft() -> list[ConnectorInfo]:
    common_fallback = "Export the data to files (PDF/DOCX/XLSX) and use the Documents import folder."
    return [
        ConnectorInfo(
            key="outlook", name="Outlook (Email)", category="microsoft", status=NOT_CONFIGURED,
            auth_type="delegated (Auth Code + PKCE)", permissions=["Mail.Read", "offline_access"],
            admin_consent="tenant-dependent (often required)",
            purpose="Read approved mail from your own mailbox",
            note="Delegated, read-only, your mailbox only. Not enabled until authorized.",
            action_required=("ACTION REQUIRED FROM M365 ADMIN: register app; grant delegated "
                             "Mail.Read + offline_access; admin consent per tenant policy."),
            fallback="Export mailbox/folder to PST or emails to PDF. " + common_fallback),
        ConnectorInfo(
            key="teams", name="Microsoft Teams", category="microsoft", status=NOT_CONFIGURED,
            auth_type="delegated", permissions=["ChannelMessage.Read.All", "Chat.Read"],
            admin_consent="yes + Protected-API approval",
            purpose="Read approved channel/chat messages",
            note="Strongest gating: admin consent AND Microsoft Protected-API approval; Teams "
                 "license required. Not all chat types are reachable under one permission.",
            action_required=("ACTION REQUIRED FROM M365 ADMIN: register app; grant "
                             "ChannelMessage.Read.All + Chat.Read; admin consent; submit Microsoft "
                             "Protected-API access request for the specific team/channel."),
            fallback="Manually capture the valuable threads to a note/PDF. " + common_fallback),
        ConnectorInfo(
            key="onenote", name="OneNote", category="microsoft", status=NOT_CONFIGURED,
            auth_type="delegated (Auth Code + PKCE)", permissions=["Notes.Read", "offline_access"],
            admin_consent="tenant-dependent",
            purpose="Read approved notebooks (yours)",
            note="OneNote returns HTML per page and needs its own parser. Delegated, read-only.",
            action_required=("ACTION REQUIRED FROM M365 ADMIN: register app; grant delegated "
                             "Notes.Read; admin consent per tenant policy."),
            fallback="Export pages/sections to PDF or Word. " + common_fallback),
        ConnectorInfo(
            key="sharepoint", name="SharePoint", category="microsoft", status=NOT_CONFIGURED,
            auth_type="delegated / app (Sites.Selected)", permissions=["Sites.Selected"],
            admin_consent="yes",
            purpose="Read an approved site / document library",
            note="Use Sites.Selected (specific sites only). Do NOT combine with Files.Read.All.",
            action_required=("ACTION REQUIRED FROM M365 ADMIN: register app; grant Sites.Selected; "
                             "admin consent; grant the app access to the specific site(s) only."),
            fallback="Use OneDrive/SharePoint Sync to a local folder, or download files. "
                     + common_fallback),
        ConnectorInfo(
            key="onedrive", name="OneDrive", category="microsoft", status=NOT_CONFIGURED,
            auth_type="delegated (Auth Code + PKCE)", permissions=["Files.Read", "offline_access"],
            admin_consent="tenant-dependent",
            purpose="Read approved OneDrive files (yours)",
            note="Delegated, read-only, your OneDrive only.",
            action_required=("ACTION REQUIRED FROM M365 ADMIN: register app; grant delegated "
                             "Files.Read; admin consent per tenant policy."),
            fallback="Sync or download the files. " + common_fallback),
    ]


def all_status() -> dict:
    from backend.services import registry as doc_registry

    stats = doc_registry.stats()
    local = ConnectorInfo(
        key="local", name="Local Documents & Import Folder", category="local", status=AVAILABLE,
        auth_type="none", permissions=[], admin_consent="no",
        purpose="Upload files, or drop exports into data/import/ and bulk-import",
        note=f"{stats['documents']} documents / {stats['chunks']} chunks indexed. "
             "This works with no Microsoft access at all.")
    return {"local": [local.to_dict()], "microsoft": [c.to_dict() for c in _microsoft()]}
