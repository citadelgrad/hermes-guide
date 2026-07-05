#!/usr/bin/env bash
# Populate the hermes-guide knowledge graph with docs + skills.
# Usage: scripts/seed.sh
# Requires: HERMES_GUIDE_ADMIN_TOKEN set (retrieve from 1Password).
# Takes ~2.5 hours. Scales machine up before seeding and back down after.
set -euo pipefail

APP=hermes-guide
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_DIR="$REPO_DIR/pipeline"

: "${HERMES_GUIDE_ADMIN_TOKEN:?HERMES_GUIDE_ADMIN_TOKEN must be set — check your .envrc}"

export HERMES_GUIDE_URL="https://${APP}.fly.dev"

scale_down() {
  echo "Scaling back down..."
  fly scale vm shared-cpu-1x --vm-memory 1024 -a "$APP" || true
}
trap scale_down EXIT

echo "Scaling up for seeding..."
fly scale vm performance-2x --vm-memory 4096 -a "$APP"

echo "Running docs pipeline..."
cd "$REPO_DIR"
uv run --no-project --with-requirements pipeline/requirements-pipeline.txt python "$PIPELINE_DIR/run-docs-pipeline.py"

echo "Running skills pipeline..."
uv run --no-project --with-requirements pipeline/requirements-pipeline.txt python "$PIPELINE_DIR/run-skills-pipeline.py"

printf '\n✓ Seeding complete.\n'
