# =====================================================================================
# INSTALL-PROBES - copies ONLY the Phase 0 probe files into the SHVDN scripts folder.
# NOT LSAX PRODUCTION CODE. Disposable validation tooling.
#   <scripts>\LsaxPhase0Probe.dll            (P-SL-01 / P-ID-01 / P-SL-02 probe; P-SL-02 stays disabled)
#   <scripts>\LSAXProbeSql\*                 (P-DB-01 probe + its 9 dependency files, isolated folder)
#   <scripts>\LSAXProbe\probe.ini            (from install\config\probe.<profile>.ini)
#   <scripts>\LSAXProbe\LSAX-PACK-INSTALL-MANIFEST.tsv, install-report-*.txt, install-backup\ (own bookkeeping)
# Never touches saves, GTA executables, ScriptHookV, SHVDN, their INI files or any other mod file.
# Exit codes: 0 ok, 1 invalid input/environment, 2 pack payload invalid, 3 game running, 4 declined, 5 copy failed.
# =====================================================================================
param(
    [string]$GtaRoot,
    [ValidateSet('All', 'Main', 'Sql')][string]$Component = 'All',
    [string]$ProbeProfile = 'PSL01',
    [switch]$UseLocalBuild,
    [switch]$AssumeYes
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

Write-Lsax ($script:LsaxPackName + ' - INSTALL-PROBES')
Write-Lsax 'Installs disposable Phase 0 probes only. Nothing here is LSAX production code.'
Assert-GameNotRunning
$pack = Get-PackRoot
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $AssumeYes
$ini = Read-ShvdnIni $gta
Write-Lsax ('GTA folder      : ' + $gta)
Write-Lsax ('SHVDN scripts   : ' + $scripts)

# ---------------------------------------------------------------- payload selection and verification
$rows = @(Read-DeploymentManifest $pack)
$wanted = @()
foreach ($r in $rows) {
    if ($Component -eq 'All' -or ($Component -eq 'Main' -and $r.Component -eq 'main') -or ($Component -eq 'Sql' -and $r.Component -eq 'sql')) {
        $wanted += $r
    }
}
if ($wanted.Count -eq 0) {
    Exit-Lsax 2 'DEPLOYMENT-MANIFEST.tsv lists no files for this component.'
}

$plan = @()
foreach ($r in $wanted) {
    Assert-OwnDest $r.Dest
    if ($UseLocalBuild) {
        $sub = 'build-local/main'
        if ($r.Component -eq 'sql') {
            $sub = 'build-local/sql'
        }
        $src = Join-Rel $pack ($sub + '/' + (Split-Path -Leaf $r.Source))
    }
    else {
        $src = Join-Rel $pack $r.Source
    }
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        Exit-Lsax 2 ('Payload file missing: ' + $src)
    }
    $h = Get-Sha256 $src
    if ((-not $UseLocalBuild) -and ($h -ne $r.Sha256)) {
        Exit-Lsax 2 ('SHA-256 mismatch for ' + $r.Source + ': expected ' + $r.Sha256 + ' got ' + $h + '. Re-extract the pack.')
    }
    $dest = Join-Rel $scripts $r.Dest
    $state = 'NEW'
    if (Test-Path -LiteralPath $dest -PathType Leaf) {
        if ((Get-Sha256 $dest) -eq $h) {
            $state = 'IDENTICAL'
        }
        else {
            $state = 'REPLACE'
        }
    }
    $plan += New-Object PSObject -Property @{ Component = $r.Component; Src = $src; DestRel = $r.Dest; Dest = $dest; Sha256 = $h; State = $state }
}
if ($UseLocalBuild) {
    Write-LsaxWarn 'Using the LOCAL build from build-local\ instead of the pack payload. Record this and the hashes below in ENVIRONMENT.txt.'
}

# probe.ini from the selected profile
$profileText = Get-ProfileText $pack $ProbeProfile $scripts
$iniRel = $script:ProbeDirName + '/probe.ini'
$iniDest = Join-Rel $scripts $iniRel
$iniHash = Get-TextSha256 $profileText
$iniState = 'NEW'
if (Test-Path -LiteralPath $iniDest -PathType Leaf) {
    if ((Get-Sha256 $iniDest) -eq $iniHash) {
        $iniState = 'IDENTICAL'
    }
    else {
        $iniState = 'REPLACE'
    }
}

# ---------------------------------------------------------------- read-only scan of the scripts folder
$ownDll = @('LsaxPhase0Probe.dll', 'LsaxPhase0SqliteProbe.dll')
$ownDestRel = @($rows | ForEach-Object { $_.Dest.ToLowerInvariant() })
$depNames = @($rows | Where-Object { $_.Component -eq 'sql' } | ForEach-Object { Split-Path -Leaf $_.Dest } | Where-Object { $ownDll -notcontains $_ })
$duplicates = @()
$sameNameDeps = @()
foreach ($f in (Get-ChildItem -LiteralPath $scripts -Recurse -File -Filter '*.dll' -ErrorAction SilentlyContinue)) {
    if ($f.Name -notlike '*.dll') {
        continue
    }
    $rel = Get-RelPath $scripts $f.FullName
    if ($ownDestRel -contains $rel.ToLowerInvariant()) {
        continue
    }
    if ($ownDll -contains $f.Name) {
        $duplicates += $rel
    }
    elseif ($depNames -contains $f.Name) {
        $ver = '<unknown>'
        try {
            $ver = $f.VersionInfo.FileVersion
        }
        catch {
            $ver = '<unreadable>'
        }
        $sameNameDeps += ($rel + "`tfileVersion=" + $ver)
    }
}
foreach ($d in @($script:ProbeDirName, $script:SqlDirName)) {
    $p = Join-Path $scripts $d
    if (Test-Path -LiteralPath $p -PathType Container) {
        foreach ($f in (Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue)) {
            if ($f.Extension -ieq '.cs' -or $f.Extension -ieq '.vb') {
                Exit-Lsax 1 ('Source file inside a probe folder would be compiled by SHVDN: ' + (Get-RelPath $scripts $f.FullName) + ' - remove it first.')
            }
        }
    }
}
if ($duplicates.Count -gt 0) {
    foreach ($d in $duplicates) {
        Write-LsaxWarn ('Another copy of a probe DLL exists: <scripts>\' + $d)
    }
    Exit-Lsax 1 'Probe DLL copies outside the pack destinations would load twice. Remove them yourself (this script never deletes files it did not install) and run again.'
}
$sqlDir = Join-Path $scripts $script:SqlDirName
if (Test-Path -LiteralPath $sqlDir -PathType Container) {
    foreach ($f in (Get-ChildItem -LiteralPath $sqlDir -File -ErrorAction SilentlyContinue)) {
        $rel = Get-RelPath $scripts $f.FullName
        if ($ownDestRel -notcontains $rel.ToLowerInvariant()) {
            Write-LsaxWarn ('Unknown file in the probe folder (left untouched): <scripts>\' + $rel)
        }
    }
}

# ---------------------------------------------------------------- show the plan, ask
Write-Lsax ('Component: ' + $Component + '   probe.ini profile: ' + $ProbeProfile)
Write-Lsax 'Every destination (nothing else is written):'
foreach ($p in $plan) {
    Write-Lsax ('  [' + $p.State + '] ' + $p.Dest)
}
Write-Lsax ('  [' + $iniState + '] ' + $iniDest + '   (profile ' + $ProbeProfile + ')')
Write-Lsax ('  [BOOKKEEPING] ' + (Get-InstallManifestPath $scripts))
Write-Lsax ('  [BOOKKEEPING] ' + (Join-Rel $scripts ($script:ProbeDirName + '/install-report-<UTC>.txt')))
if (($plan | Where-Object { $_.State -eq 'REPLACE' }) -or $iniState -eq 'REPLACE') {
    Write-Lsax ('  REPLACE = an existing file of the same name is first backed up to <scripts>\' + $script:ProbeDirName + '\install-backup\<UTC>\*.lsaxbak')
}
if ($sameNameDeps.Count -gt 0) {
    Write-LsaxWarn 'Same-name dependency DLLs of other mods exist (R-COMP-2 evidence; they are NOT touched):'
    foreach ($d in $sameNameDeps) {
        Write-LsaxWarn ('  <scripts>\' + $d)
    }
}
if (-not (Read-Confirm 'Install exactly the files listed above?' 'YES' $AssumeYes)) {
    Exit-Lsax 4 'Aborted by the owner. Nothing was written.'
}

# ---------------------------------------------------------------- execute
$stamp = Get-UtcStamp
$manifest = Read-InstallManifest $scripts
$failed = $null
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $scripts $script:ProbeDirName) | Out-Null
    if ($plan | Where-Object { $_.Component -eq 'sql' }) {
        New-Item -ItemType Directory -Force -Path $sqlDir | Out-Null
    }
    foreach ($p in $plan) {
        $bak = '-'
        if ($manifest.Contains($p.DestRel)) {
            $bak = $manifest[$p.DestRel].Backup
        }
        if ($p.State -eq 'REPLACE') {
            $bak = Backup-OwnFile $scripts $p.DestRel $stamp
        }
        if ($p.State -ne 'IDENTICAL') {
            Copy-Item -LiteralPath $p.Src -Destination $p.Dest -Force
        }
        if ((Get-Sha256 $p.Dest) -ne $p.Sha256) {
            throw ('post-copy SHA-256 mismatch: ' + $p.Dest)
        }
        if ($script:OnWindows -and (Get-Command Unblock-File -ErrorAction SilentlyContinue)) {
            Unblock-File -LiteralPath $p.Dest
        }
        $manifest[$p.DestRel] = New-Object PSObject -Property @{ Dest = $p.DestRel; Sha256 = $p.Sha256; Component = $p.Component; Backup = $bak; InstalledUtc = $stamp }
        Write-Lsax ('  ok ' + $p.DestRel)
    }
    $bak = '-'
    if ($manifest.Contains($iniRel)) {
        $bak = $manifest[$iniRel].Backup
    }
    if ($iniState -eq 'REPLACE') {
        $bak = Backup-OwnFile $scripts $iniRel $stamp
    }
    Write-TextFile $iniDest $profileText
    $manifest[$iniRel] = New-Object PSObject -Property @{ Dest = $iniRel; Sha256 = $iniHash; Component = 'config'; Backup = $bak; InstalledUtc = $stamp }
    Write-Lsax ('  ok ' + $iniRel + ' (profile ' + $ProbeProfile + ')')
}
catch {
    $failed = $_.Exception.Message
}
finally {
    Write-InstallManifest $scripts $manifest
}
if ($failed) {
    Exit-Lsax 5 ('Install failed: ' + $failed + ' - the manifest lists what was installed; REMOVE-PROBES.cmd removes it.')
}

# ---------------------------------------------------------------- report (no absolute paths: they may contain the user name)
$consoleKey = 'F4 (SHVDN default)'
if ($ini.ConsoleKeyBinding) {
    $consoleKey = $ini.ConsoleKeyBinding + ' (ScriptHookVDotNet.ini)'
}
$rep = New-Object System.Text.StringBuilder
[void]$rep.Append("$($script:LsaxPackName) install report (OFFLINE bookkeeping; not runtime evidence)`r`n")
[void]$rep.Append("installed_utc`t$stamp`r`ncomponent`t$Component`r`nprofile`t$ProbeProfile`r`nlocal_build`t$([bool]$UseLocalBuild)`r`n")
[void]$rep.Append("scripts_location_ini`t$(if ($ini.ScriptsLocation) { 'custom' } else { 'default (scripts)' })`r`n")
[void]$rep.Append("console_key`t$consoleKey`r`nreload_key`t$(if ($ini.ReloadKeyBinding) { $ini.ReloadKeyBinding } else { 'none (SHVDN default)' })`r`n")
foreach ($k in $manifest.Keys) {
    [void]$rep.Append("file`t" + $manifest[$k].Dest + "`t" + $manifest[$k].Sha256 + "`r`n")
}
foreach ($d in $sameNameDeps) {
    [void]$rep.Append("same_name_dependency_of_other_mod`t" + $d + "`r`n")
}
Write-TextFile (Join-Rel $scripts ($script:ProbeDirName + '/install-report-' + $stamp + '.txt')) $rep.ToString()

foreach ($k in @('LsaxPhase0Probe.dll', ($script:SqlDirName + '/LsaxPhase0SqliteProbe.dll'))) {
    if ($manifest.Contains($k)) {
        Write-Lsax ('SHA-256 ' + $k + ' = ' + $manifest[$k].Sha256 + '   (copy into ENVIRONMENT.txt)')
    }
}
Write-Lsax ('SHVDN console key: ' + $consoleKey + '. Console commands: Reload()  ListScripts()')
Exit-Lsax 0 'Probe files installed. Nothing has been validated yet: start GTA V and follow 01-SMOKE-TEST-RU.md.'
