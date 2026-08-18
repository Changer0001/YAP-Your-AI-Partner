# SOP: POS Terminal Connectivity Troubleshooting (SYNTHETIC)

Site: Property A — Downtown Hotel · Status: Approved · Version: 2.1 · Updated: 2026-06-15

When a POS terminal cannot connect to the network, check the following **in order**:

1. **Verify the switch access port is on VLAN 55** (the POS VLAN). On SW-CORE-A / SW-ACCESS-A1,
   the port should read `switchport access vlan 55`. A wrong VLAN is the most common cause.
2. **Confirm the terminal has an IP in 10.20.55.0/24.** If it shows a 169.254.x.x address, DHCP
   failed — check the FortiGate DHCP scope for VLAN 55 (10.20.55.50–200).
3. **Check the cable and the switch port link light.** Reseat or move to a known-good port.
4. **Confirm the uplink trunk carries VLAN 55** to the core (`switchport trunk allowed vlan` must
   include 55).
5. **If the whole site is affected**, check the FortiGate (10.20.0.1) and core switch SW-CORE-A
   (10.20.0.2).

Escalate to the network team if the terminal still cannot reach the POS server after these steps.
