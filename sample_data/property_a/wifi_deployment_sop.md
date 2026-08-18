# SOP: Wi-Fi Access Point Deployment (SYNTHETIC)

Site: Property A — Downtown Hotel · Status: Approved · Version: 1.4

## SSIDs
- **DTWN-Staff** → VLAN 10 (STAFF), WPA2-Enterprise
- **DTWN-Guest** → VLAN 20 (GUEST), captive portal, client isolation ON

## Deploying a new Aruba AP
1. Connect the AP to an access-switch port configured as a **trunk** allowing VLANs 10 and 20,
   native VLAN 90 (management).
2. The AP pulls management IP from VLAN 90 DHCP and registers with the controller at **10.20.90.5**.
3. Confirm the AP appears in the controller and both SSIDs broadcast.
4. Guest traffic (VLAN 20) must remain isolated from internal VLANs — verify the FortiGate policy
   blocks GUEST → STAFF/POS/VOICE.

Wi-Fi password for the staff SSID is stored in the credential vault, not in this document.
