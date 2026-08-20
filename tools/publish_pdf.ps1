# End-of-day publish: commit and push the source, then refresh the PDF branch.
# `pixi run publish [message]` builds first (pixi.toml), so a broken document
# stops before anything is committed. PDFs go to `pdf` as a single parentless
# force-pushed commit, so that branch never grows and no PDF enters source
# history.

param(
	[Parameter(ValueFromRemainingArguments = $true)]
	[string[]]$MessageParts
)

$ErrorActionPreference = 'Stop'

# guards below report by throwing; show the reason, not a PowerShell stack trace
trap {
	Write-Host ''
	Write-Host "publish aborted: $($_.Exception.Message)" -ForegroundColor Red
	exit 1
}

$root = Split-Path -Parent $PSScriptRoot
$pdfBranch = 'pdf'

# files to publish: <path in build/> -> <path on the pdf branch>
$files = [ordered]@{
	'thesis\main.pdf'   = 'thesis.pdf'
	'meetings\main.pdf' = 'meetings.pdf'
}

function Invoke-Git {
	$out = git -C $root @args
	if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') failed" }
	return $out
}

# --- 1. commit the source ------------------------------------------------

$branch = Invoke-Git rev-parse --abbrev-ref HEAD
if ($branch -eq 'HEAD') { throw 'detached HEAD - check out a branch before publishing' }

# a rebase/merge left half-finished would otherwise be committed as-is
if (Test-Path (Join-Path $root '.git\MERGE_HEAD')) { throw 'merge in progress - resolve it first' }
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
	Write-Host "no source changes to commit"
}

Invoke-Git push origin HEAD | Out-Null
Write-Host "pushed $branch"

# --- 2. gate -------------------------------------------------------------

# by now the tree must be clean, so the sha stamped on the PDFs really does
# describe the source they were built from
$dirty = Invoke-Git status --porcelain
if ($dirty) { throw "working tree still dirty after commit - refusing to publish PDFs:`n$($dirty -join "`n")" }

$srcRev = Invoke-Git rev-parse --short HEAD

# --- 3. publish the PDFs -------------------------------------------------

# a temporary index keeps the working tree and checked-out branch untouched
$tmpIndex = Join-Path $env:TEMP "publish-pdf-index-$PID"
$env:GIT_INDEX_FILE = $tmpIndex
try {
	Invoke-Git read-tree --empty | Out-Null

	$published = @()
	foreach ($src in $files.Keys) {
		$path = Join-Path $root "build\$src"
		if (-not (Test-Path $path)) {
			Write-Host "skip  build/$src (not built)"
			continue
		}
		$blob = Invoke-Git hash-object -w -- $path
		Invoke-Git update-index --add --cacheinfo "100644,$blob,$($files[$src])" | Out-Null
		$published += $files[$src]
	}

	if ($published.Count -eq 0) { throw 'no PDFs in build/ - run `pixi run build` first' }

	$tree = Invoke-Git write-tree
} finally {
	Remove-Item Env:\GIT_INDEX_FILE -ErrorAction SilentlyContinue
	if (Test-Path $tmpIndex) { Remove-Item $tmpIndex -Force }
}

# no -p: parentless, so the branch is always exactly one commit deep
$commit = Invoke-Git commit-tree $tree -m "built PDFs from $srcRev"
Invoke-Git push --force origin "${commit}:refs/heads/$pdfBranch" | Out-Null

$url = (Invoke-Git remote get-url origin) -replace '\.git$', ''
Write-Host ''
Write-Host "pushed $pdfBranch (built from $srcRev)"
foreach ($f in $published) { Write-Host "  $url/blob/$pdfBranch/$f" }
