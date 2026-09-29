# =====================================================================================
# REMOVE-PROBES - removes exactly the files INSTALL-PROBES installed (paths from the install manifest),
# and only while their SHA-256 still equals the installed one. Never wildcard-deletes a folder, never
# touches saves, GTA, ScriptHookV, SHVDN, their INI files or any other mod.
# NOT LSAX PRODUCTION CODE.
#   default          : delete the installed probe files (DLLs, LSAXProbeSql\*, probe.ini) and the manifest;
#                      logs/evidence, install reports and install backups are KEPT.
#   -RestoreBackups  : also put back files that INSTALL-PROBES backed up (only where the path is now free).
#   -DeleteEvidence  : also delete the probe logs/evidence (current run and runs\*), the probe's own p0*.db files,
#                      install reports and install backups - listed file by file, after typing DELETE EVIDENCE.
#                      Run COLLECT-EVIDENCE.cmd first. -AssumeYes never answers this question.
# Exit codes: 0 ok, 3 game running, 4 declined, 6 nothing installed, 8 finished but some changed files were kept.
# =====================================================================================
param(
    [string]$GtaRoot,
    [switch]$RestoreBackups,
    [switch]$DeleteEvidence,
    [switch]$AssumeYes
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

Write-Lsax ($script:LsaxPackName + ' - REMOVE-PROBES')
Assert-GameNotRunning
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $AssumeYes
$probeDir = Join-Path $scripts $script:ProbeDirName
$manifest = Read-InstallManifest $scripts
if ($manifest.Count -eq 0) {
    Exit-Lsax 6 'No install manifest found in <scripts>\LSAXProbe - nothing installed by this pack here. Nothing was deleted.'
}

$delete = @()
$kept = @()
foreach ($k in $manifest.Keys) {
    $e = $manifest[$k]
    Assert-OwnDest $e.Dest
    $p = Join-Rel $scripts $e.Dest
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        Write-Lsax ('  [ALREADY GONE] ' + $e.Dest)
        continue
    }
    if ((Get-Sha256 $p) -eq $e.Sha256) {
        $delete += $p
        Write-Lsax ('  [DELETE] ' + $p)
    }
    else {
        $kept += $e.Dest
        Write-LsaxWarn ('  [KEEP - changed since install, not deleted] ' + $p)
    }
}
$restore = @()
if ($RestoreBackups) {
    foreach ($k in $manifest.Keys) {
        $e = $manifest[$k]
        if ($e.Backup -and $e.Backup -ne '-') {
            Assert-OwnDest $e.Backup
            $b = Join-Rel $scripts $e.Backup
            if (Test-Path -LiteralPath $b -PathType Leaf) {
                $restore += New-Object PSObject -Property @{ From = $b; To = (Join-Rel $scripts $e.Dest); Rel = $e.Dest }
                Write-Lsax ('  [RESTORE BACKUP] ' + $e.Backup + ' -> ' + $e.Dest)
            }
        }
    }
}
if (-not (Read-Confirm 'Delete exactly the files marked [DELETE] above?' 'YES' $AssumeYes)) {
    Exit-Lsax 4 'Aborted by the owner. Nothing was deleted.'
}
foreach ($p in $delete) {
    Remove-Item -LiteralPath $p
}
foreach ($r in $restore) {
    if (Test-Path -LiteralPath $r.To) {
        Write-LsaxWarn ('  not restored (path in use): ' + $r.Rel)
        continue
    }
    Copy-Item -LiteralPath $r.From -Destination $r.To
    Write-Lsax ('  restored ' + $r.Rel)
}
if ($kept.Count -eq 0) {
    Remove-Item -LiteralPath (Get-InstallManifestPath $scripts)
    Write-Lsax ('  deleted ' + $script:ProbeDirName + '\' + $script:ManifestName)
}
else {
    $left = [ordered]@{}
    foreach ($k in $manifest.Keys) {
        if ($kept -contains $manifest[$k].Dest) {
            $left[$k] = $manifest[$k]
        }
    }
    Write-InstallManifest $scripts $left
}

# ---------------------------------------------------------------- evidence (explicit, file by file)
if ($DeleteEvidence) {
    $ev = @()
    $ev += @(Get-RunFiles $probeDir $true)
    $runsDir = Join-Path $probeDir 'runs'
    if (Test-Path -LiteralPath $runsDir -PathType Container) {
        foreach ($d in (Get-ChildItem -LiteralPath $runsDir -Directory)) {
            $ev += @(Get-RunFiles $d.FullName $true)
        }
    }
    foreach ($f in (Get-ChildItem -LiteralPath $probeDir -File -Filter 'install-report-*.txt' -ErrorAction SilentlyContinue)) {
        if ($f.Name -like 'install-report-*.txt') {
            $ev += $f.FullName
        }
    }
    $bakDir = Join-Path $probeDir 'install-backup'
    if (Test-Path -LiteralPath $bakDir -PathType Container) {
        foreach ($d in (Get-ChildItem -LiteralPath $bakDir -Directory)) {
            foreach ($f in (Get-ChildItem -LiteralPath $d.FullName -File -Filter '*.lsaxbak')) {
                if ($f.Name -like '*.lsaxbak') {
                    $ev += $f.FullName
                }
            }
        }
    }
    if ($ev.Count -gt 0) {
        Write-LsaxWarn 'EVIDENCE FILES that will be deleted (run COLLECT-EVIDENCE.cmd first!):'
        foreach ($f in $ev) {
            Write-LsaxWarn ('  ' + $f)
        }
        $answer = Read-Host 'Type DELETE EVIDENCE to delete exactly these files, anything else keeps them'
        if ($answer -ceq 'DELETE EVIDENCE') {
            foreach ($f in $ev) {
                Remove-Item -LiteralPath $f
            }
            Write-Lsax ('  deleted ' + $ev.Count + ' evidence/backup file(s)')
        }
        else {
            Write-Lsax '  evidence kept'
        }
    }
}

# ---------------------------------------------------------------- remove our folders only if empty (never recursive)
$dirs = @()
foreach ($base in @((Join-Path $probeDir 'runs'), (Join-Path $probeDir 'install-backup'))) {
    if (Test-Path -LiteralPath $base -PathType Container) {
        foreach ($d in (Get-ChildItem -LiteralPath $base -Directory)) {
            $dirs += $d.FullName
        }
        $dirs += $base
    }
}
$dirs += @((Join-Path $scripts $script:SqlDirName), $probeDir)
foreach ($d in $dirs) {
    if ((Test-Path -LiteralPath $d -PathType Container) -and -not (Get-ChildItem -LiteralPath $d -Force)) {
        Remove-Item -LiteralPath $d
        Write-Lsax ('  removed empty folder ' + $d)
    }
}
if (Test-Path -LiteralPath $probeDir -PathType Container) {
    Write-Lsax ('Kept: ' + $probeDir + ' (evidence, backups or files the pack did not create).')
}
Write-Lsax 'Saves are never touched by this pack: restore your profile/save backup yourself (09-REMOVE-AND-RESTORE-RU.md).'
Write-Lsax 'The session-token decorator exists only while the game runs; it is gone after a restart.'
if ($kept.Count -gt 0) {
    Exit-Lsax 8 ('Probe files removed, but ' + $kept.Count + ' changed file(s) were kept (listed above). Delete them yourself only if you are sure.')
}
Exit-Lsax 0 'Probe files removed.'
