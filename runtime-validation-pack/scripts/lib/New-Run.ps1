# =====================================================================================
# START-NEW-RUN - starts a clean probe run by MOVING (never deleting) the current run files of
# <scripts>\LSAXProbe\ into <scripts>\LSAXProbe\runs\<label>-<UTC>\ .
# NOT LSAX PRODUCTION CODE.
# Moved: probe-*.log, sqlite-probe.log, probe-ledger.tsv, session-token.txt, domains-*.count and the probe's own
# SQLite files p0*.db*. Not moved: probe.ini, the install manifest, install reports, install-backup\.
# COLLECT-EVIDENCE.cmd collects the current run AND every runs\ folder, so nothing is lost.
# Exit codes: 0 ok (also when there was nothing to move), 1 invalid input, 3 game running, 4 declined, 6 not installed.
# =====================================================================================
param(
    [string]$GtaRoot,
    [Parameter(Mandatory = $true)][string]$Label,
    [switch]$AssumeYes
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

if ($Label -notmatch '^[A-Za-z0-9_-]{1,40}$') {
    Exit-Lsax 1 '-Label must be 1-40 characters A-Z a-z 0-9 _ - (example: FULL-MODPACK-T01-T17).'
}
Write-Lsax ($script:LsaxPackName + ' - START-NEW-RUN ' + $Label)
Assert-GameNotRunning
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $AssumeYes
$probeDir = Join-Path $scripts $script:ProbeDirName
if (-not (Test-Path -LiteralPath (Get-InstallManifestPath $scripts) -PathType Leaf)) {
    Exit-Lsax 6 'The probes are not installed by this pack here (no manifest). Run INSTALL-PROBES.cmd first.'
}
$files = @(Get-RunFiles $probeDir $true)
if ($files.Count -eq 0) {
    Exit-Lsax 0 'No run files present - the next game start begins a clean run.'
}
$target = Join-Rel $probeDir ('runs/' + $Label + '-' + (Get-UtcStamp))
$n = 2
$first = $target
while (Test-Path -LiteralPath $target) {
    $target = $first + '-' + $n
    $n++
}
Write-Lsax ('These files will be MOVED (not deleted) to ' + $target + ' :')
foreach ($f in $files) {
    Write-Lsax ('  ' + (Split-Path -Leaf $f))
}
if (-not (Read-Confirm 'Move them and start a clean run?' 'YES' $AssumeYes)) {
    Exit-Lsax 4 'Aborted by the owner. Nothing was moved.'
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
foreach ($f in $files) {
    Move-Item -LiteralPath $f -Destination (Join-Path $target (Split-Path -Leaf $f))
}
Exit-Lsax 0 ('Moved ' + $files.Count + ' file(s). The next game start begins run "' + $Label + '".')
