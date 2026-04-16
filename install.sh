#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/Chemokoren/claw-code-parity.git"
DEFAULT_INSTALL_DIR="$HOME/.local/share/claw-code-parity"
DEFAULT_BIN_DIR="$HOME/.local/bin"
DEFAULT_COMMAND_NAME="claw-code-parity"

REPO_URL="${CLAW_REPO_URL:-$DEFAULT_REPO_URL}"
INSTALL_DIR="${CLAW_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
BIN_DIR="${CLAW_BIN_DIR:-$DEFAULT_BIN_DIR}"
COMMAND_NAME="${CLAW_COMMAND_NAME:-$DEFAULT_COMMAND_NAME}"
BRANCH="${CLAW_GIT_BRANCH:-}"
PYTHON_BIN="${CLAW_SETUP_PYTHON:-python3}"

info() {
  printf '[info] %s\n' "$*"
}

warn() {
  printf '[warn] %s\n' "$*" >&2
}

die() {
  printf '[error] %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: ./install.sh [options]

Clone claw-code-parity into a designated per-user directory and run setup.sh
there to create the virtual environment and global launcher.
Run this as your normal user; the script uses sudo itself when apt packages are needed.

Options:
  --repo-url URL       Git repository URL
                       Default: $DEFAULT_REPO_URL
  --branch NAME        Git branch to install
                       Default: repository default branch
  --install-dir PATH   Target install directory
                       Default: $DEFAULT_INSTALL_DIR
  --bin-dir PATH       Directory for the launcher script
                       Default: $DEFAULT_BIN_DIR
  --command-name NAME  Launcher command name
                       Default: $DEFAULT_COMMAND_NAME
  --python BIN         Python interpreter to pass to setup.sh
                       Default: python3
  --help               Show this help text
EOF
}

invoking_user_home() {
  if [ -n "${SUDO_USER:-}" ] && command -v getent >/dev/null 2>&1; then
    getent passwd "$SUDO_USER" | cut -d: -f6
    return
  fi

  printf '%s\n' "$HOME"
}

ensure_not_running_as_root() {
  local user_home

  if [ "$(id -u)" -ne 0 ] && [ -z "${SUDO_USER:-}" ]; then
    return
  fi

  user_home="$(invoking_user_home)"
  die "install.sh is a per-user installer and should not be run with sudo or as root.

Run it as your normal user:
  ./install.sh

It will use sudo automatically if Ubuntu packages need to be installed.

Expected per-user install location:
  ${user_home}/.local/share/claw-code-parity"
}

python_supports_venv() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || return 1
  "$PYTHON_BIN" -c 'import ensurepip, venv' >/dev/null 2>&1
}

python_venv_package_name() {
  local version_tag

  version_tag="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [ -n "$version_tag" ]; then
    printf 'python%s-venv\n' "$version_tag"
    return
  fi

  printf 'python3-venv\n'
}

expand_path() {
  case "$1" in
    "~")
      printf '%s\n' "$HOME"
      ;;
    "~/"*)
      printf '%s/%s\n' "$HOME" "${1#~/}"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

resolve_path() {
  local raw expanded parent base

  raw="$(expand_path "$1")"
  if [ -d "$raw" ]; then
    (
      cd "$raw"
      pwd
    )
    return
  fi

  parent="$(dirname "$raw")"
  base="$(basename "$raw")"
  mkdir -p "$parent"
  parent="$(
    cd "$parent"
    pwd
  )"
  printf '%s/%s\n' "$parent" "$base"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo-url)
      [ "$#" -ge 2 ] || die "--repo-url requires a value"
      REPO_URL="$2"
      shift 2
      ;;
    --branch)
      [ "$#" -ge 2 ] || die "--branch requires a value"
      BRANCH="$2"
      shift 2
      ;;
    --install-dir)
      [ "$#" -ge 2 ] || die "--install-dir requires a value"
      INSTALL_DIR="$2"
      shift 2
      ;;
    --bin-dir)
      [ "$#" -ge 2 ] || die "--bin-dir requires a value"
      BIN_DIR="$2"
      shift 2
      ;;
    --command-name)
      [ "$#" -ge 2 ] || die "--command-name requires a value"
      COMMAND_NAME="$2"
      shift 2
      ;;
    --python)
      [ "$#" -ge 2 ] || die "--python requires a value"
      PYTHON_BIN="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

ensure_not_running_as_root
INSTALL_DIR="$(resolve_path "$INSTALL_DIR")"
BIN_DIR="$(resolve_path "$BIN_DIR")"

ensure_system_packages() {
  local need=()
  local prefix=()

  if ! command -v git >/dev/null 2>&1; then
    need+=(git)
  fi

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if [ "$PYTHON_BIN" = "python3" ]; then
      need+=(python3 python3-venv)
    else
      die "Requested Python interpreter not found: $PYTHON_BIN"
    fi
  elif ! python_supports_venv; then
    need+=("$(python_venv_package_name)")
  fi

  if [ "${#need[@]}" -gt 0 ]; then
    local deduped=()
    local item
    local seen=" "

    for item in "${need[@]}"; do
      case "$seen" in
        *" $item "*) ;;
        *)
          deduped+=("$item")
          seen="${seen}${item} "
          ;;
      esac
    done
    need=("${deduped[@]}")
  fi

  if [ "${#need[@]}" -eq 0 ]; then
    return
  fi

  command -v apt-get >/dev/null 2>&1 || die "apt-get is required to install missing packages: ${need[*]}"

  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install missing packages: ${need[*]}"
    prefix=(sudo)
  fi

  info "Installing missing system packages: ${need[*]}"
  "${prefix[@]}" apt-get update
  "${prefix[@]}" apt-get install -y "${need[@]}"

  if ! python_supports_venv; then
    die "Installed packages, but $PYTHON_BIN still cannot create virtual environments.

Please verify this package is installed successfully:
  sudo apt install $(python_venv_package_name)"
  fi
}

detect_default_branch() {
  git ls-remote --symref "$REPO_URL" HEAD 2>/dev/null | awk '/^ref:/ {sub("refs/heads/", "", $2); print $2; exit}'
}

ensure_branch_value() {
  if [ -n "$BRANCH" ]; then
    return
  fi

  BRANCH="$(detect_default_branch || true)"
  if [ -z "$BRANCH" ]; then
    BRANCH="main"
    warn "Could not detect the repository default branch; falling back to '$BRANCH'"
  fi
}

clone_or_update_repo() {
  local backup_dir

  if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing checkout in $INSTALL_DIR"
    git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
    git -C "$INSTALL_DIR" fetch --tags origin
    if git -C "$INSTALL_DIR" show-ref --verify --quiet "refs/heads/$BRANCH"; then
      git -C "$INSTALL_DIR" checkout "$BRANCH"
    else
      git -C "$INSTALL_DIR" checkout -b "$BRANCH" "origin/$BRANCH"
    fi
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
    return
  fi

  if [ -e "$INSTALL_DIR" ]; then
    backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d%H%M%S)"
    warn "Existing non-git directory found at $INSTALL_DIR"
    warn "Moving it to $backup_dir"
    mv "$INSTALL_DIR" "$backup_dir"
  fi

  info "Cloning $REPO_URL ($BRANCH) into $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
}

run_setup() {
  info "Running setup.sh"
  "$INSTALL_DIR/setup.sh" \
    --install-dir "$INSTALL_DIR" \
    --bin-dir "$BIN_DIR" \
    --command-name "$COMMAND_NAME" \
    --python "$PYTHON_BIN"
}

ensure_system_packages
ensure_branch_value
clone_or_update_repo
run_setup
