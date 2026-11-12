# Sync with GitHub and Overleaf: commit local work, pull --rebase from GitHub,
# merge Overleaf's edits, merge the bibliography with thesis-papers
# (tools/papers.py), push to both.
# `pixi run sync [message]`. Committing first keeps uncommitted work out of
# the rebase; safe to run when there is nothing to do.

param(
	[Parameter(ValueFromRemainingArguments = $true)]
	[string[]]$MessageParts
)

$ErrorActionPreference = 'Stop'

# guards below report by throwing; show the reason, not a PowerShell stack trace
trap {
	Write-Host ''
	Write-Host "sync aborted: $($_.Exception.Message)" -ForegroundColor Red
	exit 1
}

$root = Split-Path -Parent $PSScriptRoot
$BibPath = 'src/thesis/references.bib'   # this repo's copy of thesis-papers' bibliography

function Invoke-Git {
	$out = git -C $root @args
	if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') failed" }
	return $out
}

# --- 1. commit local work ------------------------------------------------

$branch = Invoke-Git rev-parse --abbrev-ref HEAD
if ($branch -eq 'HEAD') { throw 'detached HEAD - check out a branch before syncing' }

# a rebase/merge left half-finished would otherwise be committed as-is
if (Test-Path (Join-Path $root '.git\MERGE_HEAD')) { throw 'merge in progress - resolve it first' }
if (Test-Path (Join-Path $root '.git\rebase-merge')) { throw 'rebase in progress - resolve it first' }
$unmerged = Invoke-Git diff --name-only --diff-filter=U
if ($unmerged) { throw "unresolved conflicts:`n$($unmerged -join "`n")" }

Invoke-Git add -A | Out-Null
$staged = Invoke-Git diff --cached --name-status

if ($staged) {
	Write-Host "committing to $branch :"
	$staged | ForEach-Object { Write-Host "  $_" }

	if ($MessageParts) {
		$msg = $MessageParts -join ' '
	} else {
		$msg = "wip: $(Get-Date -Format 'yyyy-MM-dd')"
	}
	Invoke-Git commit -m $msg | Out-Null
	Write-Host "committed: $msg"
} else {
	Write-Host 'no local changes to commit'
}

# --- 2. pull, rebasing local commits on top ------------------------------

# plain call so a conflict stops here with git's own instructions
git -C $root pull --rebase
if ($LASTEXITCODE -ne 0) {
	throw 'pull --rebase failed - resolve the conflict, run `git rebase --continue`, then `pixi run sync` again'
}

# Overleaf, if this clone has it as a remote (git remote add overleaf <its git
# URL>): merged, not rebased, so commits already on GitHub are never rewritten
$overleaf = (git -C $root remote) -contains 'overleaf'
if ($overleaf) {
	git -C $root pull --no-rebase --no-edit overleaf main
	if ($LASTEXITCODE -ne 0) {
		throw 'merging Overleaf failed - resolve the conflict, `git commit`, then `pixi run sync` again'
	}
}

# --- 3. the bibliography: merge with thesis-papers -------------------------

# entries added or edited here (on Overleaf, say) go to thesis-papers, and its
# own changes come here; a clash stops the sync before anything is pushed
uv run --quiet --python 3.12 --no-project python (Join-Path $root 'tools\papers.py') pull
if ($LASTEXITCODE -ne 0) { throw 'the bibliography merge stopped - see above' }
Invoke-Git add -- $BibPath | Out-Null
if (Invoke-Git diff --cached --name-only) {
	Invoke-Git commit -m 'references.bib from thesis-papers' | Out-Null
	Write-Host 'committed: references.bib from thesis-papers'
}

# --- 4. push -------------------------------------------------------------

$ahead = Invoke-Git rev-list --count '@{u}..HEAD'
if ([int]$ahead -gt 0) {
	Invoke-Git push origin HEAD | Out-Null
	Write-Host "pushed $branch ($ahead commit(s))"
} else {
	Write-Host 'nothing to push - already in sync'
}
if ($overleaf) {
	Invoke-Git push -q overleaf HEAD:main | Out-Null
	Write-Host 'Overleaf up to date'
}
