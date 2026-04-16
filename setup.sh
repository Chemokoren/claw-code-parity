#!/usr/bin/env bash
set -euo pipefail

DEFAULT_INSTALL_DIR="$HOME/.local/share/claw-code-parity"
DEFAULT_BIN_DIR="$HOME/.local/bin"
DEFAULT_COMMAND_NAME="claw-code-parity"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR"
INSTALL_DIR="${CLAW_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
BIN_DIR="${CLAW_BIN_DIR:-$DEFAULT_BIN_DIR}"
COMMAND_NAME="${CLAW_COMMAND_NAME:-$DEFAULT_COMMAND_NAME}"
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
Usage: ./setup.sh [options]

Install Claw into a designated per-user directory, create a virtual
environment there, install requirements, and create a global launcher.
Run this as your normal user, not with sudo.

Options:
  --install-dir PATH   Target install directory
                       Default: $DEFAULT_INSTALL_DIR
  --bin-dir PATH       Directory for the launcher script
                       Default: $DEFAULT_BIN_DIR
  --command-name NAME  Launcher command name
                       Default: $DEFAULT_COMMAND_NAME
  --source-dir PATH    Source checkout to install from
                       Default: the current repository checkout
  --python BIN         Python interpreter to use for venv creation
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

python_version_tag() {
  "$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
}

python_venv_package_name() {
  printf 'python%s-venv\n' "$(python_version_tag)"
}

ensure_not_running_as_root() {
  local user_home

  if [ "$(id -u)" -ne 0 ] && [ -z "${SUDO_USER:-}" ]; then
    return
  fi

  user_home="$(invoking_user_home)"
  die "setup.sh is a per-user installer and should not be run with sudo or as root.

Install the missing venv package with:
  sudo apt install $(python_venv_package_name)

Then rerun as your normal user:
  ./setup.sh

Expected per-user install location:
  ${user_home}/.local/share/claw-code-parity"
}

ensure_python_venv_support() {
  if "$PYTHON_BIN" -c 'import ensurepip, venv' >/dev/null 2>&1; then
    return
  fi

  die "Python virtual environment support is missing for $("$PYTHON_BIN" --version 2>&1).

On Ubuntu/Debian, install it with:
  sudo apt install $(python_venv_package_name)

Then rerun:
  ./setup.sh

If you prefer a one-command bootstrap, use:
  ./install.sh"
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
    --source-dir)
      [ "$#" -ge 2 ] || die "--source-dir requires a value"
      SOURCE_DIR="$2"
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

SOURCE_DIR="$(resolve_path "$SOURCE_DIR")"
INSTALL_DIR="$(resolve_path "$INSTALL_DIR")"
BIN_DIR="$(resolve_path "$BIN_DIR")"

[ -d "$SOURCE_DIR" ] || die "Source directory does not exist: $SOURCE_DIR"
[ -f "$SOURCE_DIR/claw.py" ] || die "Expected source checkout at $SOURCE_DIR (missing claw.py)"
[ -f "$SOURCE_DIR/requirements.txt" ] || die "Expected requirements.txt in $SOURCE_DIR"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python interpreter not found: $PYTHON_BIN"
ensure_not_running_as_root
ensure_python_venv_support

if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
  case "$INSTALL_DIR/" in
    "$SOURCE_DIR"/*)
      die "Install directory cannot be nested inside the source checkout"
      ;;
  esac
fi

stage_repo_copy() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT

  info "Staging repository into $INSTALL_DIR"
  tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='.port_sessions' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    -cf - -C "$SOURCE_DIR" . | tar -xf - -C "$tmp_dir"

  if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" "$tmp_dir/.env"
  elif [ ! -f "$tmp_dir/.env" ] && [ -f "$tmp_dir/.env.example" ]; then
    cp "$tmp_dir/.env.example" "$tmp_dir/.env"
  fi

  mkdir -p "$(dirname "$INSTALL_DIR")"
  rm -rf "$INSTALL_DIR"
  mv "$tmp_dir" "$INSTALL_DIR"
  trap - EXIT
}

prepare_install_tree() {
  if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
    info "Installing in place at $INSTALL_DIR"
    if [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
      cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    fi
    return
  fi

  stage_repo_copy
}

create_virtualenv() {
  info "Creating virtual environment"
  rm -rf "$INSTALL_DIR/.venv"
  "$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"

  info "Installing Python requirements"
  "$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
  "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
}

create_launcher() {
  local launcher_path
  launcher_path="$BIN_DIR/$COMMAND_NAME"

  mkdir -p "$BIN_DIR"

  cat > "$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$INSTALL_DIR/scripts/run-auto.sh" "\$@"
EOF

  chmod +x "$launcher_path"
  info "Created launcher: $launcher_path"
}

print_next_steps() {
  info "Install complete"
  printf '\n'
  printf 'Installed repo: %s\n' "$INSTALL_DIR"
  printf 'Virtualenv:     %s\n' "$INSTALL_DIR/.venv"
  printf 'Launcher:       %s/%s\n' "$BIN_DIR" "$COMMAND_NAME"
  printf 'Config file:    %s/.env\n' "$INSTALL_DIR"
  printf '\n'

  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not currently on PATH."
    printf 'Add this line to ~/.bashrc, ~/.zshrc, or your shell profile:\n'
    printf '  export PATH="%s:$PATH"\n' "$BIN_DIR"
    printf '\n'
  fi

  printf 'Run from any directory with:\n'
  printf '  %s\n' "$COMMAND_NAME"
  printf '  %s ask "explain this repo"\n' "$COMMAND_NAME"
}

prepare_install_tree
create_virtualenv
create_launcher
print_next_steps
