# Change Records — Property B — Airport Property (SYNTHETIC)

## CHG-3012 — Site build / initial config — Effective 2026-02-15 — Status: Completed
Stood up SW-CORE-B with VLANs 12 (STAFF), 22 (GUEST), 30 (VOICE), 60 (POS), 90 (MGMT).
POS on **VLAN 60**, subnet 10.30.60.0/24.

## CHG-3055 — Add voice VLAN to gate ports — Effective 2026-04-10 — Status: Completed
Configured `switchport voice vlan 30` on gate desk ports; DHCP options 66/150 point to PBX
10.30.30.10.

## CHG-3090 — FortiGate 100F policy review — Effective 2026-06-05 — Status: Completed
Reviewed and tightened GUEST isolation; POS restricted to payment gateway only.
