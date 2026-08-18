# Network Ops Meeting Notes — Property B — Airport Property — 2026-07-08 (SYNTHETIC)

Attendees: Sam Chen, Alex Rivera, site IT

## Discussion
- POS at the Airport property is stable on **VLAN 60**. No changes planned.
- Voice: a few phones at Gate 12 failed to register last week; root cause was a missing
  `switchport voice vlan 30` on two ports after a patch job. Fixed; added to the checklist.
- Guest Wi-Fi capacity is fine for current passenger volume.

## Action items
- [ ] Add a pre/post-patch VLAN verification step to the switch runbook (owner: Sam).
- [ ] Confirm FortiGate 100F is on the approved firmware (owner: Alex).
- [ ] Label the two remaining unpatched gate ports.
