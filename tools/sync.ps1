# Sync with GitHub: commit local work, pull the other machine's commits, push.
#
# Run via `pixi run sync [message]`. Local changes are committed first so a
# rebase can never touch uncommitted work; the pull rebases so history stays
# linear across desktop and laptop. Safe to run when there is nothing to do.

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

# plain `git pull --rebase` so a conflict stops here with git's own
# instructions; after resolving, `git rebase --continue` then `pixi run sync`
# again to finish the push
git -C $root pull --rebase
if ($LASTEXITCODE -ne 0) {
	throw 'pull --rebase failed - resolve the conflict, run `git rebase --continue`, then `pixi run sync` again'
}

# --- 3. push -------------------------------------------------------------

$ahead = Invoke-Git rev-list --count '@{u}..HEAD'
if ([int]$ahead -gt 0) {
	Invoke-Git push origin HEAD | Out-Null
	Write-Host "pushed $branch ($ahead commit(s))"
} else {
	Write-Host 'nothing to push - already in sync'
}
