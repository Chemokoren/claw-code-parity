#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_env ZAI_API_KEY
export_default_skill_roots
export CLAW_PROVIDER="zai"
export ZAI_BASE_URL="${ZAI_BASE_URL:-${OPENAI_BASE_URL:-$DEFAULT_ZAI_BASE_URL}}"
export OPENAI_BASE_URL="$ZAI_BASE_URL"
export ZAI_MODEL="${ZAI_MODEL:-${OPENAI_MODEL:-$DEFAULT_GLM_MODEL}}"
export OPENAI_MODEL="$ZAI_MODEL"

print_launch_context "glm-5.1"
run_claw "$@"
