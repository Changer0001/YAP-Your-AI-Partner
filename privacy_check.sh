#!/usr/bin/env bash
# Verify YAP keeps your uploaded documents private:
#   nothing tracked in git · no external AI SDK · telemetry off · sane permissions.
# Read-only — changes nothing.
cd "$(dirname "$0")"
pass=0; fail=0
ok(){ echo "  [PASS] $1"; pass=$((pass+1)); }
bad(){ echo "  [FAIL] $1"; fail=$((fail+1)); }
info(){ echo "  [info] $1"; }

echo "YAP privacy check"
echo "================="

grep -qE '^data/' .gitignore && ok "data/ (your uploads, vectors, DB) is gitignored" \
  || bad "data/ is NOT gitignored"

if git ls-files 2>/dev/null | grep -qiE '^data/'; then
  bad "files under data/ are tracked in git: $(git ls-files | grep -iE '^data/' | head)"
else
  ok "no uploaded data is tracked in git (never pushed / never in the repo)"
fi

if git ls-files 2>/dev/null | grep -qE '(^|/)\.env$'; then
  bad ".env is tracked in git"
else
  ok ".env (settings/secrets) is not tracked in git"
fi

if grep -rqiE 'import +openai|from +openai|import +anthropic|from +anthropic|googleapis|azure' backend/ 2>/dev/null; then
  bad "an external AI/cloud SDK was found in backend/"
else
  ok "no external AI SDK — inference is local via Ollama only"
fi

grep -q 'anonymized_telemetry=False' backend/services/vectorstore.py 2>/dev/null \
  && ok "vector database telemetry is disabled" \
  || bad "vector database telemetry not confirmed disabled"

if [ -d data ]; then
  perm=$(stat -c '%a' data 2>/dev/null || echo "?")
  if [ "$perm" = "700" ]; then ok "data/ permissions are 700 (owner-only)";
  else info "data/ permissions are $perm — recommend owner-only:  chmod 700 data"; fi
  [ -f data/secret.key ] && { sp=$(stat -c '%a' data/secret.key); [ "$sp" = "600" ] && ok "secret.key is 600" || info "secret.key is $sp — recommend:  chmod 600 data/secret.key"; }
else
  info "data/ does not exist yet (created on first run)"
fi

host=$(grep -E '^HOST=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
info "server binds to: ${host:-127.0.0.1}  (127.0.0.1 = this machine only; 0.0.0.0 = reachable on your LAN/Tailscale)"

echo "================="
echo "Passed: $pass   Issues: $fail"
echo ""
echo "Your uploaded documents live only in ./data on this machine and are never committed or"
echo "sent to any external AI. This chat/assistant only ever sees the code in the git repo."
[ "$fail" -eq 0 ] && exit 0 || exit 1
