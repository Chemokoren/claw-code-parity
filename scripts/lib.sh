#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_OLLAMA_BASE_URL="http://localhost:11434/v1"
DEFAULT_LOCAL_MODEL="qwen2.5-coder:7b"
DEFAULT_CLAUDE_MODEL="claude-sonnet-4-20250514"
DEFAULT_ZAI_BASE_URL="https://api.z.ai/api/coding/paas/v4"
DEFAULT_GLM_MODEL="glm-5.1"

load_repo_env_file() {
  local env_file="$ROOT_DIR/.env"
  local line key value
  local -A protected_keys=()

  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      ''|'#'*) continue ;;
      export\ *) line="${line#export }" ;;
    esac

    if [[ "$line" != *=* ]]; then
      continue
    fi

    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"

    [ -n "$key" ] || continue

    # Preserve explicitly exported shell variables over repo-local defaults,
    # while still letting later lines in `.env` override earlier ones.
    if [ -z "${protected_keys[$key]+x}" ]; then
      if [ -n "${!key+x}" ]; then
        protected_keys["$key"]=1
      else
        protected_keys["$key"]=0
      fi
    fi

    if [ "${protected_keys[$key]}" = "1" ]; then
      continue
    fi

    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$key=$value"
  done < "$env_file"
}

load_repo_env_file

info() {
  printf '[info] %s\n' "$*"
}

warn() {
  printf '[warn] %s\n' "$*" >&2
}

error() {
  printf '[error] %s\n' "$*" >&2
}

repo_root() {
  printf '%s\n' "$ROOT_DIR"
}

default_gstack_candidates() {
  cat <<EOF
${CLAW_GSTACK_ROOT:-}
$ROOT_DIR/.agents/skills/gstack
$HOME/.codex/skills/gstack
$HOME/.claude/skills/gstack
/home/kibsoft/Documents/projects/gstack/gstack
EOF
}

detect_gstack_root() {
  local candidate
  while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    if [ -f "$candidate/SKILL.md" ] || [ -x "$candidate/setup" ] || [ -d "$candidate/bin" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(default_gstack_candidates)
  return 1
}

export_default_skill_roots() {
  if [ -n "${CLAW_SKILL_ROOTS:-}" ]; then
    return 0
  fi

  local gstack_root
  if gstack_root="$(detect_gstack_root 2>/dev/null)"; then
    export CLAW_SKILL_ROOTS="$gstack_root"
  fi
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    error "Required command not found on PATH: $command_name"
    exit 1
  fi
}

require_env() {
  local key="$1"
  if [ -z "${!key:-}" ]; then
    error "Required environment variable is not set: $key"
    exit 1
  fi
}

resolved_model() {
  case "${CLAW_PROVIDER:-}" in
    anthropic)
      printf '%s\n' "${CLAW_MODEL:-$DEFAULT_CLAUDE_MODEL}"
      ;;
    zai)
      printf '%s\n' "${ZAI_MODEL:-${OPENAI_MODEL:-$DEFAULT_GLM_MODEL}}"
      ;;
    *)
      printf '%s\n' "${OPENAI_MODEL:-${CLAW_MODEL:-<unset>}}"
      ;;
  esac
}

resolved_base_url() {
  case "${CLAW_PROVIDER:-}" in
    anthropic)
      printf '%s\n' "${ANTHROPIC_BASE_URL:-https://api.anthropic.com/v1}"
      ;;
    zai)
      printf '%s\n' "${ZAI_BASE_URL:-${OPENAI_BASE_URL:-$DEFAULT_ZAI_BASE_URL}}"
      ;;
    ollama|auto)
      printf '%s\n' "${OLLAMA_BASE_URL:-$DEFAULT_OLLAMA_BASE_URL}"
      ;;
    *)
      printf '%s\n' "${OPENAI_BASE_URL:-${OLLAMA_BASE_URL:-<unset>}}"
      ;;
  esac
}

print_launch_context() {
  local mode="$1"
  info "repo: $ROOT_DIR"
  info "mode: $mode"
  info "provider: ${CLAW_PROVIDER:-<unset>}"
  info "model: $(resolved_model)"
  info "base URL: $(resolved_base_url)"
  if [ -n "${CLAW_SKILL_ROOTS:-}" ]; then
    info "skills: $CLAW_SKILL_ROOTS"
  fi
}

run_claw() {
  cd "$ROOT_DIR"
  python3 -m src.main "$@"
}
