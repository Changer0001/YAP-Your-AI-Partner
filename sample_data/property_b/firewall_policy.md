# FortiGate FW-B Policy Summary — Property B — Airport Property (SYNTHETIC)

Device: FortiGate 100F · Mgmt: 10.30.0.1

## DHCP scopes
| VLAN | Subnet | Range |
|------|--------|-------|
| 12 STAFF | 10.30.12.0/24 | .50–.200 |
| 22 GUEST | 10.30.22.0/24 | .50–.240 |
| 30 VOICE | 10.30.30.0/24 | .50–.150 (options 66/150 → 10.30.30.10) |
| 60 POS | 10.30.60.0/24 | .50–.200 |

## Key policies
- GUEST (VLAN 22) → internal VLANs: denied.
- POS (VLAN 60) → payment gateway only; POS → Internet: denied.
- VOICE (VLAN 30) → PBX (10.30.30.10): allowed.
- Admin access restricted to MGMT VLAN 90.
