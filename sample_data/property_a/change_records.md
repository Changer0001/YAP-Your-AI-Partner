# Change Records — Property A — Downtown Hotel (SYNTHETIC)

Approved network changes, most recent first.

## CHG-2041 — POS VLAN migration — Effective 2026-03-01 — Status: Completed
POS terminals were migrated from the legacy **VLAN 50** to **VLAN 55**. All POS access ports and the
FortiGate DHCP scope were updated. **Current POS VLAN is 55.** (Supersedes the old VLAN 50 design.)

## CHG-2088 — EtherChannel to distribution — Effective 2026-05-12 — Status: Completed
Bundled Gi1/0/23-24 on SW-CORE-A into Port-channel1 (LACP active) uplink to SW-DIST-A.
Trunk allows VLANs 10,20,30,55,90.

## CHG-2103 — FortiGate firmware upgrade — Effective 2026-06-20 — Status: Completed
FW-A (FortiGate 60F) upgraded to the current approved firmware. No policy changes.

## CHG-2140 — Guest Wi-Fi isolation hardening — Effective 2026-07-02 — Status: Completed
Added explicit deny policies so GUEST (VLAN 20) cannot reach STAFF, POS, or VOICE.
