# =====================================================================================
# SET-PROBE-CONFIG - replaces <scripts>\LSAXProbe\probe.ini with one of the pack profiles.
# NOT LSAX PRODUCTION CODE. Profiles: PSL01 (B-01 runs, T1-T17), PDB01-STEP1, PDB01, PDB01-LEAK (P-DB-01),
# PID01 (P-ID-01). No profile enables P-SL-02 (AnchorProbe) - see 08-P-SL-02-OPTIONAL-RU.md.
# The previous probe.ini is backed up when it differs. Only probe.ini and the pack manifest are written.
# Exit codes: 0 ok, 1 invalid input, 2 pack invalid, 3 game running, 4 declined, 6 probes not installed.
# =====================================================================================
param(
    [string]$GtaRoot,
    [Parameter(Mandatory = $true)][string]$ProbeProfile,
    [switch]$AssumeYes
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

Write-Lsax ($script:LsaxPackName + ' - SET-PROBE-CONFIG ' + $ProbeProfile)
Assert-GameNotRunning
$pack = Get-PackRoot
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $AssumeYes
$manifest = Read-InstallManifest $scripts
if (-not $manifest.Contains('LsaxPhase0Probe.dll')) {
    Exit-Lsax 6 'The probes are not installed by this pack in this scripts folder (no manifest entry). Run INSTALL-PROBES.cmd first.'
}
$text = Get-ProfileText $pack $ProbeProfile $scripts
if ($ProbeProfile -like 'PDB01*' -and -not $manifest.Contains($script:SqlDirName + '/LsaxPhase0SqliteProbe.dll')) {
    Exit-Lsax 6 'Profile needs the SQLite probe, which is not installed. Run INSTALL-PROBES.cmd -Component All (or Sql).'
}
$iniRel = $script:ProbeDirName + '/probe.ini'
$iniDest = Join-Rel $scripts $iniRel
$newHash = Get-TextSha256 $text
$bak = '-'
if ($manifest.Contains($iniRel)) {
    $bak = $manifest[$iniRel].Backup
}
if (Test-Path -LiteralPath $iniDest -PathType Leaf) {
    if ((Get-Sha256 $iniDest) -eq $newHash) {
        Write-Lsax ('probe.ini already equals profile ' + $ProbeProfile + ' - nothing to do.')
        Exit-Lsax 0 ('Active profile: ' + $ProbeProfile)
    }
    $bak = Backup-OwnFile $scripts $iniRel (Get-UtcStamp)
}
Write-Lsax ('Destination: ' + $iniDest)
Write-TextFile $iniDest $text
$manifest[$iniRel] = New-Object PSObject -Property @{ Dest = $iniRel; Sha256 = $newHash; Component = 'config'; Backup = $bak; InstalledUtc = (Get-UtcStamp) }
Write-InstallManifest $scripts $manifest
foreach ($line in ($text -split "`r?`n")) {
    if ($line -match '^\s*(SqliteProbe|IdentityProbe|AnchorProbe|SessionToken)\.[A-Za-z]+\s*=') {
        Write-Lsax ('  ' + $line.Trim())
    }
}
Exit-Lsax 0 ('Active profile: ' + $ProbeProfile + '. The probes read probe.ini when their script domain starts (game start, load, Reload()).')
