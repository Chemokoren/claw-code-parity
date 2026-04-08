#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_env ANTHROPIC_API_KEY
export_default_skill_roots
export CLAW_PROVIDER="anthropic"
export CLAW_MODEL="${CLAW_MODEL:-$DEFAULT_CLAUDE_MODEL}"

print_launch_context "anthropic"
run_claw "$@"
