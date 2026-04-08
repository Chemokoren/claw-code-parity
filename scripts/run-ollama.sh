#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_command ollama
export_default_skill_roots
export CLAW_PROVIDER="ollama"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-$DEFAULT_OLLAMA_BASE_URL}"
export OPENAI_BASE_URL="$OLLAMA_BASE_URL"
export OPENAI_MODEL="${OPENAI_MODEL:-$DEFAULT_LOCAL_MODEL}"

if ! ollama ps >/dev/null 2>&1; then
  warn "Ollama is not responding at ${OLLAMA_BASE_URL}. Start it with 'ollama serve' or your system service."
fi

print_launch_context "ollama"
run_claw "$@"
