# YAP sample data (SYNTHETIC — not real)

Fake but realistic IT data to test YAP. **None of this is real** — invented sites, devices, IPs,
VLANs, and emails. Safe to use for demos and testing.

## What's here
- `property_a/` — "Downtown Hotel" knowledge base (network docs, Cisco config, SOPs, inventory)
- `property_b/` — "Airport Property" knowledge base (note: **POS VLAN is different here** — good for
  testing that properties stay isolated)
- `emails/` — `.eml` files (a switch-migration thread + a POS incident) to test **Import email**

## How to test in ~5 minutes
1. **Properties** → create two: `Downtown Hotel` and `Airport Property`.
2. Pick **Downtown Hotel** in the top-bar picker → **Documents**:
   - drop the files in `property_a/` into `data/import/` and click **Import from folder** (or upload them), and
   - **Import email** → upload each file in `emails/`.
3. Switch to **Airport Property** → import `property_b/`.
4. **Chat** and try:
   - "What VLAN is used for POS at this property?" → **55** on Downtown, **60** on Airport (proves isolation)
   - "Which VLANs are configured on SW-CORE-A?" → 10, 20, 30, 55, 90
   - "How do I troubleshoot a POS terminal that can't connect?"
   - "When was the switch migration rescheduled to?" → **Tuesday** (from the email thread)
   - "What was the resolution of the POS connectivity incident?" → access port was on the wrong VLAN
   - "What is the capital of France?" → should refuse (not in the knowledge base)
5. Check the **Sources** under each answer — they should cite the exact file/email.
