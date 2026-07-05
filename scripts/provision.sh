#!/usr/bin/env bash
# First-deploy provisioning for hermes-guide on Fly.io.
# Usage: scripts/provision.sh [region]   (default: dfw)
# Requires: flyctl authenticated, GEMINI_API_KEY in environment.
set -euo pipefail

REGION=${1:-dfw}
APP=hermes-guide
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
ENVRC="$SCRIPT_DIR/../.envrc"

: "${GEMINI_API_KEY:?GEMINI_API_KEY must be set (check your .envrc)}"

cd "$BACKEND_DIR"

# Create app if it doesn't exist
if ! fly status -a "$APP" &>/dev/null; then
  fly apps create --name "$APP"
fi

# Create volume if not exists
if ! fly volumes list -a "$APP" 2>/dev/null | grep -q lightrag_data; then
  fly volumes create lightrag_data --region "$REGION" --size 10 --yes -a "$APP"
fi

# Generate admin token (query endpoint is public; only ingest needs auth)
ADMIN_TOKEN="$(openssl rand -hex 32)"

# Persist to .envrc so seed script can read it
{
  echo ""
  echo "export HERMES_GUIDE_URL=\"https://${APP}.fly.dev\""
  echo "export HERMES_GUIDE_ADMIN_TOKEN=\"${ADMIN_TOKEN}\""
} >> "$ENVRC"
echo "✓ Tokens written to .envrc"

fly secrets set \
  HERMES_GUIDE_ADMIN_TOKEN="$ADMIN_TOKEN" \
  GEMINI_API_KEY="$GEMINI_API_KEY" \
  LIGHTRAG_DATA_DIR="/data" \
  EMBEDDING_RATE_LIMIT_DELAY="0" \
  MAX_ASYNC="2" \
  -a "$APP"

fly deploy --ha=false -a "$APP"

printf '\n✓ Deployed to https://%s.fly.dev\n' "$APP"
printf '  Verify: curl -s https://%s.fly.dev/health\n' "$APP"
printf '  Verify: curl -s https://%s.fly.dev/ready\n' "$APP"
printf '\nNext: make seed  (HERMES_GUIDE_ADMIN_TOKEN is in .envrc)\n'
