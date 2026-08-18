# PBX / Voice DHCP Guide (SYNTHETIC)

Site: Property B — Airport Property · Version: 1.0

- Voice VLAN: **30** (subnet 10.30.30.0/24). PBX server: 10.30.30.10.
- Phones must receive DHCP **option 66** (TFTP server name) and **option 150** (TFTP server IP)
  pointing to 10.30.30.10 so they can download their configuration.
- Switch access ports for phones use `switchport voice vlan 30` with the data VLAN as the access
  VLAN (typically STAFF VLAN 12).

## Phone won't register
1. Confirm the port has `switchport voice vlan 30`.
2. Verify the phone gets an IP in 10.30.30.0/24 and DHCP options 66/150 are present.
3. Ping the PBX (10.30.30.10) from the voice VLAN.
4. Check the FortiGate allows VOICE → PBX.
