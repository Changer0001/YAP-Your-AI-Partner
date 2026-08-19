#!/usr/bin/env bash
# Apply the SAFE, reversible privacy hardening, then run the privacy check.
# (Encryption at rest and the outbound firewall are documented in docs/DATA_SECURITY.md —
#  they are not auto-applied because they can lock you out if done carelessly.)
set -e
cd "$(dirname "$0")"

echo "==> Restricting data/ to owner-only (chmod 700)"
mkdir -p data
chmod 700 data
[ -f data/secret.key ] && chmod 600 data/secret.key || true
chmod 600 .env 2>/dev/null || true

echo "==> Verifying nothing sensitive is tracked in git"
if git ls-files 2>/dev/null | grep -qiE '^data/|(^|/)\.env$'; then
  echo "    WARNING: something under data/ or a .env is tracked — remove it with: git rm --cached <file>"
fi

echo ""
echo "Applied. For stronger protection see docs/DATA_SECURITY.md:"
echo "  - Encryption at rest (full-disk LUKS, or gocryptfs on the data folder)"
echo "  - Optional strict outbound firewall (with the Tailscale/updates caveats)"
echo ""
./privacy_check.sh
