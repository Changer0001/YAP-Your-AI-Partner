# Runbook: Access Switch Replacement — Property A — Downtown Hotel (SYNTHETIC)

Version: 1.2 · Status: Approved

## Before the maintenance window
1. Back up the running config of the switch being replaced.
2. Confirm the replacement switch runs the standard approved IOS version.
3. Stage the config: VLANs 10,20,30,55,90; uplink trunk; POS access ports on VLAN 55 with PortFast
   + BPDU Guard.

## During
1. Label and photograph all cables.
2. Power down the old switch; rack the replacement.
3. Apply the staged config; connect the uplink trunk to SW-CORE-A first.
4. Move access ports; verify each POS port shows `switchport access vlan 55`.

## Verify
1. Each POS terminal pulls a 10.20.55.x address and reaches the POS server.
2. Wi-Fi APs re-register with the controller (10.20.90.5).
3. Spanning tree is stable; SW-CORE-A remains root.

## Rollback
If POS does not come up within 15 minutes, reconnect the old switch and reschedule.
