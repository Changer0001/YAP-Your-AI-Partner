"""Connector framework — authorization is separate from ingestion.

A connector describes a data source, its required permissions, and its live status. Microsoft
connectors are metadata-only until an admin-approved, least-privilege authorization exists (see
docs/MICROSOFT_365_AUTHORIZATION.md). No connector accesses real company data in this repo.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

# status values
AVAILABLE = "available"          # usable now
NOT_CONFIGURED = "not_configured"  # supported, needs setup/approval
BLOCKED = "blocked"              # an authorization/consent requirement is unmet


@dataclass
class ConnectorInfo:
    key: str
    name: str
    category: str               # "local" | "microsoft"
    status: str                 # AVAILABLE | NOT_CONFIGURED | BLOCKED
    auth_type: str = "none"     # e.g. "delegated (Auth Code + PKCE)"
    permissions: list[str] = field(default_factory=list)
    admin_consent: str = "no"   # "no" | "tenant-dependent" | "yes" | "yes + protected API"
    purpose: str = ""
    note: str = ""
    action_required: Optional[str] = None
    fallback: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class BaseConnector:
    """Interface a real connector implements. Fetching is always user-initiated and scoped."""
    info: ConnectorInfo

    def status(self) -> ConnectorInfo:
        return self.info

    def authorize(self):  # pragma: no cover - implemented per connector
        raise NotImplementedError

    def fetch(self, scope: dict):  # pragma: no cover
        raise NotImplementedError

    def normalize(self, raw) -> list[dict]:  # pragma: no cover
        raise NotImplementedError
