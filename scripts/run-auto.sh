#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

export_default_skill_roots
export CLAW_PROVIDER="auto"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-$DEFAULT_OLLAMA_BASE_URL}"
export OPENAI_MODEL="${OPENAI_MODEL:-$DEFAULT_LOCAL_MODEL}"

print_launch_context "auto"
run_claw "$@"
