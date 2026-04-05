#!/usr/bin/env bash
# update.sh — Pull latest from main and merge into dev
set -euo pipefail

MAIN_BRANCH="main"
DEV_BRANCH="dev"
REMOTE="origin"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# Ensure we're in a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    error "Not a git repository."
    exit 1
fi

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    warn "You have uncommitted changes. Stashing them first..."
    git stash push -m "update.sh: auto-stash before merge $(date +%F_%T)"
    STASHED=true
else
    STASHED=false
fi

# Make sure we're on dev
CURRENT=$(git branch --show-current)
if [ "$CURRENT" != "$DEV_BRANCH" ]; then
    warn "Currently on '$CURRENT', switching to '$DEV_BRANCH'..."
    git checkout "$DEV_BRANCH"
fi

# Fetch latest from remote
info "Fetching latest from $REMOTE..."
git fetch "$REMOTE"

# Update local main
info "Updating local $MAIN_BRANCH..."
git checkout "$MAIN_BRANCH"
git pull "$REMOTE" "$MAIN_BRANCH"

# Switch back to dev and merge
info "Merging $MAIN_BRANCH into $DEV_BRANCH..."
git checkout "$DEV_BRANCH"

if git merge "$MAIN_BRANCH" --no-edit; then
    info "Merge successful!"
else
    error "Merge conflicts detected. Resolve them, then run:"
    echo "    git add . && git commit"
    if [ "$STASHED" = true ]; then
        warn "You have stashed changes. After resolving conflicts, run: git stash pop"
    fi
    exit 1
fi

# Restore stashed changes if any
if [ "$STASHED" = true ]; then
    info "Restoring stashed changes..."
    if git stash pop; then
        info "Stashed changes restored."
    else
        warn "Stash pop had conflicts. Resolve manually with: git stash show -p | git apply"
    fi
fi

echo ""
info "Done! Your '$DEV_BRANCH' branch is up to date with '$MAIN_BRANCH'."
