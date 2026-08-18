# Property B — Airport Property — Network Overview (SYNTHETIC)

Site code: AIR-B

## Core infrastructure
- Firewall: FortiGate 100F — management 10.30.0.1
- Core switch: SW-CORE-B (Cisco Catalyst 9300) — management 10.30.0.2
- Wireless: Aruba APs, controller at 10.30.90.5

## VLANs (note: different scheme from Downtown)
| VLAN | Name | Subnet | Purpose |
|------|------|--------|---------|
| 12 | STAFF | 10.30.12.0/24 | Staff / admin |
| 22 | GUEST | 10.30.22.0/24 | Guest Wi-Fi |
| 30 | VOICE | 10.30.30.0/24 | VoIP phones / PBX |
| 60 | POS | 10.30.60.0/24 | Point-of-sale terminals |
| 90 | MGMT | 10.30.0.0/24 | Network management |

## Key facts
- **POS terminals at this property use VLAN 60** (not 55 — that is the Downtown scheme).
- Voice VLAN is 30; phones receive DHCP option 66/150 pointing to the PBX at 10.30.30.10.
- The core switch SW-CORE-B is the spanning-tree root for all VLANs.
