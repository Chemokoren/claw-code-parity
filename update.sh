#!/usr/bin/env bash
# update.sh — Pull latest from upstream/main and merge into your dev branch
#
# Workflow:
#   origin   = YOUR fork (where you push your changes)
#   upstream = the original repo (where you pull updates from)
#
# First-time setup (run once):
#   git remote add upstream https://github.com/ultraworkers/claw-code-parity.git
#   git remote set-url origin https://github.com/YOUR_USERNAME/claw-code-parity.git
#
set -euo pipefail

UPSTREAM="upstream"
ORIGIN="origin"
MAIN_BRANCH="main"
DEV_BRANCH="dev"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
step()  { echo -e "${CYAN}[→]${NC} $1"; }

# ── Preflight checks ───────────────────────────────────────────────

# Ensure we're in a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    error "Not a git repository."
    exit 1
fi

# Check that 'upstream' remote exists; if not, set it up
if ! git remote get-url "$UPSTREAM" &>/dev/null; then
    warn "'$UPSTREAM' remote not found. Adding it now..."
    # Default to the original repo URL
    UPSTREAM_URL="https://github.com/ultraworkers/claw-code-parity.git"
    git remote add "$UPSTREAM" "$UPSTREAM_URL"
    info "Added remote '$UPSTREAM' → $UPSTREAM_URL"
fi

echo ""
step "Remotes:"
git remote -v | sed 's/^/    /'
echo ""

# ── Stash uncommitted changes ──────────────────────────────────────

if ! git diff --quiet || ! git diff --cached --quiet; then
    warn "You have uncommitted changes. Stashing them first..."
    git stash push -m "update.sh: auto-stash before merge $(date +%F_%T)"
    STASHED=true
else
    STASHED=false
fi

# ── Make sure we're on dev ─────────────────────────────────────────

CURRENT=$(git branch --show-current)
if [ "$CURRENT" != "$DEV_BRANCH" ]; then
    warn "Currently on '$CURRENT', switching to '$DEV_BRANCH'..."
    git checkout "$DEV_BRANCH"
fi

# ── Fetch latest from upstream ─────────────────────────────────────

step "Fetching latest from $UPSTREAM..."
git fetch "$UPSTREAM"

# ── Merge upstream/main into dev ───────────────────────────────────

step "Merging $UPSTREAM/$MAIN_BRANCH into $DEV_BRANCH..."

if git merge "$UPSTREAM/$MAIN_BRANCH" --no-edit; then
    info "Merge successful!"
else
    error "Merge conflicts detected. Resolve them, then run:"
    echo "    git add . && git commit"
    if [ "$STASHED" = true ]; then
        warn "You have stashed changes. After resolving conflicts, run: git stash pop"
    fi
    exit 1
fi

# ── Restore stashed changes ───────────────────────────────────────

if [ "$STASHED" = true ]; then
    step "Restoring stashed changes..."
    if git stash pop; then
        info "Stashed changes restored."
    else
        warn "Stash pop had conflicts. Resolve manually with: git stash show -p | git apply"
    fi
fi

# ── Summary ────────────────────────────────────────────────────────

echo ""
info "Done! Your '$DEV_BRANCH' branch is up to date with '$UPSTREAM/$MAIN_BRANCH'."
echo ""
echo -e "  ${CYAN}Next steps:${NC}"
echo "    git push origin $DEV_BRANCH    # push your updated dev to your fork"
echo ""
