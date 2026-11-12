#!/usr/bin/env bash
# Sync with GitHub and Overleaf: commit local work, pull --rebase from GitHub,
# merge Overleaf's edits, merge the bibliography with thesis-papers
# (tools/papers.py), push to both. The Linux twin of
# sync.ps1. `pixi run sync [message]`. Committing first keeps uncommitted work
# out of the rebase; safe to run when there is nothing to do.
set -euo pipefail

abort() { printf '\nsync aborted: %s\n' "$1" >&2; exit 1; }

root="$(cd "$(dirname "$0")/.." && pwd)"
g() { git -C "$root" "$@" || abort "git $* failed"; }
bib='src/thesis/references.bib'   # this repo's copy of thesis-papers' bibliography

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

# Overleaf, if this clone has it as a remote (git remote add overleaf <its git
# URL>): merged, not rebased, so commits already on GitHub are never rewritten
overleaf="$(git -C "$root" remote | grep -x overleaf || true)"
if [ -n "$overleaf" ]; then
	git -C "$root" pull --no-rebase --no-edit overleaf main \
		|| abort 'merging Overleaf failed - resolve the conflict, `git commit`, then `pixi run sync` again'
fi

# --- 3. the bibliography: merge with thesis-papers -------------------------

# entries added or edited here (on Overleaf, say) go to thesis-papers, and its
# own changes come here; a clash stops the sync before anything is pushed
uv run --quiet --python 3.12 --no-project python "$root/tools/papers.py" pull \
	|| abort 'the bibliography merge stopped - see above'
g add -- "$bib"
if [ -n "$(g diff --cached --name-only)" ]; then
	g commit -q -m 'references.bib from thesis-papers'
	echo 'committed: references.bib from thesis-papers'
fi

# --- 4. push -------------------------------------------------------------

ahead="$(g rev-list --count '@{u}..HEAD')"
if [ "$ahead" -gt 0 ]; then
	g push -q origin HEAD
	echo "pushed $branch ($ahead commit(s))"
else
	echo 'nothing to push - already in sync'
fi
if [ -n "$overleaf" ]; then
	g push -q overleaf HEAD:main
	echo 'Overleaf up to date'
fi
