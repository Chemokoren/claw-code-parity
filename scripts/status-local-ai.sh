#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

export_default_skill_roots

info "repo: $(repo_root)"
info "python: $(command -v python3 || echo unavailable)"
info "ZAI_API_KEY: $( [ -n "${ZAI_API_KEY:-}" ] && echo set || echo unset )"
info "ANTHROPIC_API_KEY: $( [ -n "${ANTHROPIC_API_KEY:-}" ] && echo set || echo unset )"

if command -v codex >/dev/null 2>&1; then
  info "codex: $(command -v codex)"
  codex --version || true
else
  warn "codex not found on PATH"
fi

if command -v claude >/dev/null 2>&1; then
  info "claude: $(command -v claude)"
  claude --version || true
else
  warn "claude not found on PATH"
fi

if command -v ollama >/dev/null 2>&1; then
  info "ollama: $(command -v ollama)"
  ollama --version || true
  info "ollama models:"
  ollama list || true
  info "ollama running models:"
  ollama ps || true
else
  warn "ollama not found on PATH"
fi

cd "$(repo_root)"
python3 - <<'PY'
from src.config import ClawConfig
cfg = ClawConfig()
print(cfg.summary())
PY
