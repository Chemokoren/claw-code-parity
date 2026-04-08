#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_command bash
local_gstack_root="$(detect_gstack_root || true)"
if [ -z "$local_gstack_root" ]; then
  error "Could not find a gstack checkout. Set CLAW_GSTACK_ROOT=/path/to/gstack and retry."
  exit 1
fi

if [ ! -x "$local_gstack_root/setup" ]; then
  error "gstack setup script is missing or not executable: $local_gstack_root/setup"
  exit 1
fi

info "using gstack root: $local_gstack_root"
exec "$local_gstack_root/setup" --host codex "$@"
