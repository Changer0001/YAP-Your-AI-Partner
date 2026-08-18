# FortiGate FW-A Policy Summary — Property A — Downtown Hotel (SYNTHETIC)

Device: FortiGate 60F · Mgmt: 10.20.0.1 · Version: approved firmware (see CHG-2103)

## DHCP scopes
| VLAN | Subnet | Range | Gateway |
|------|--------|-------|---------|
| 10 STAFF | 10.20.10.0/24 | .50–.200 | 10.20.10.1 |
| 20 GUEST | 10.20.20.0/24 | .50–.240 | 10.20.20.1 |
| 55 POS | 10.20.55.0/24 | .50–.200 | 10.20.55.1 |

## Key policies
- STAFF → Internet: allowed (web filtering profile "corp").
- GUEST → Internet: allowed; GUEST → STAFF/POS/VOICE: **denied** (see CHG-2140).
- POS → POS server (10.20.55.10) and payment gateway: allowed; POS → Internet: denied.
- VOICE → PBX: allowed.

## Notes
- All admin access to FW-A is restricted to the MGMT VLAN (90).
- Credentials are stored in the credential vault, never in this document.
