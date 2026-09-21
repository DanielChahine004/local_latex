#!/usr/bin/env bash
# Sync with GitHub: commit local work, pull --rebase, push. The Linux twin of
# sync.ps1. `pixi run sync [message]`. Committing first keeps uncommitted work
# out of the rebase; safe to run when there is nothing to do.
set -euo pipefail

abort() { printf '\nsync aborted: %s\n' "$1" >&2; exit 1; }

root="$(cd "$(dirname "$0")/.." && pwd)"
g() { git -C "$root" "$@" || abort "git $* failed"; }

# --- 1. commit local work ------------------------------------------------

branch="$(g rev-parse --abbrev-ref HEAD)"
[ "$branch" = HEAD ] && abort 'detached HEAD - check out a branch before syncing'

# a rebase/merge left half-finished would otherwise be committed as-is
[ -e "$root/.git/MERGE_HEAD" ] && abort 'merge in progress - resolve it first'
[ -e "$root/.git/rebase-merge" ] && abort 'rebase in progress - resolve it first'
unmerged="$(g diff --name-only --diff-filter=U)"
[ -n "$unmerged" ] && abort "unresolved conflicts:"$'\n'"$unmerged"

g add -A
staged="$(g diff --cached --name-status)"

if [ -n "$staged" ]; then
	echo "committing to $branch :"
	sed 's/^/  /' <<<"$staged"
	msg="${*:-wip: $(date +%F)}"
	g commit -q -m "$msg"
	echo "committed: $msg"
else
	echo 'no local changes to commit'
fi

# --- 2. pull, rebasing local commits on top ------------------------------

# plain call so a conflict stops here with git's own instructions
git -C "$root" pull --rebase \
	|| abort 'pull --rebase failed - resolve the conflict, run `git rebase --continue`, then `pixi run sync` again'

# --- 3. push -------------------------------------------------------------

ahead="$(g rev-list --count '@{u}..HEAD')"
if [ "$ahead" -gt 0 ]; then
	g push -q origin HEAD
	echo "pushed $branch ($ahead commit(s))"
else
	echo 'nothing to push - already in sync'
fi
