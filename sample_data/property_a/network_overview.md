# Property A — Downtown Hotel — Network Overview (SYNTHETIC)

Site code: DTWN-A

## Core infrastructure
- Firewall: FortiGate 60F — management 10.20.0.1
- Core switch: SW-CORE-A (Cisco Catalyst 9300) — management 10.20.0.2
- Access switch: SW-ACCESS-A1 (Cisco Catalyst 9200) — management 10.20.0.3
- Wireless: Aruba APs managed by controller at 10.20.90.5

## VLANs
| VLAN | Name | Subnet | Purpose |
|------|------|--------|---------|
| 10 | STAFF | 10.20.10.0/24 | Staff / admin workstations |
| 20 | GUEST | 10.20.20.0/24 | Guest Wi-Fi |
| 30 | VOICE | 10.20.30.0/24 | VoIP phones / PBX |
| 55 | POS | 10.20.55.0/24 | Point-of-sale terminals |
| 90 | MGMT | 10.20.0.0/24 | Network management |

## Key facts
- **POS terminals use VLAN 55.** DHCP for VLAN 55 is served by the FortiGate (scope 10.20.55.50–200).
- The uplink from SW-ACCESS-A1 to SW-CORE-A is a **trunk** carrying VLANs 10, 20, 30, 55, 90.
- Guest Wi-Fi (VLAN 20) is isolated from all internal VLANs by FortiGate policy.
- Spanning tree: Rapid-PVST; SW-CORE-A is the root bridge for all VLANs.
