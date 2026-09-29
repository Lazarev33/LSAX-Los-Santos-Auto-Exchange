# =====================================================================================
# LSAX PHASE 0 RUNTIME VALIDATION PACK - shared helper functions.
# NOT LSAX PRODUCTION CODE. Disposable validation tooling for the Phase 0 probes only.
# Compatible with Windows PowerShell 5.1 and PowerShell 7. ASCII only (PS 5.1 reads
# BOM-less scripts as ANSI).
# Safety rules implemented here (see 00-RUN-ME-FIRST-RU.md):
#   - never guess the GTA path: it comes from -GtaRoot or from an interactive prompt;
#   - never write outside <scripts>\LsaxPhase0Probe.dll, <scripts>\LSAXProbeSql\ and <scripts>\LSAXProbe\;
#   - never read, copy or modify save files, GTA executables, ScriptHookV, SHVDN or their INI files
#     (ScriptHookVDotNet.ini is READ ONLY to find the scripts folder).
# =====================================================================================

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:LsaxPackName = 'LSAX-PHASE0-RUNTIME-VALIDATION-PACK'
$script:OnWindows = ($env:OS -eq 'Windows_NT')
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:ManifestName = 'LSAX-PACK-INSTALL-MANIFEST.tsv'
$script:ProbeDirName = 'LSAXProbe'
$script:SqlDirName = 'LSAXProbeSql'
$script:ProfileNames = @('PSL01', 'PDB01-STEP1', 'PDB01', 'PDB01-LEAK', 'PID01')
$script:ConfigNames = @('FULL-MODPACK', 'MINIMAL')
# Files the probes themselves write into <scripts>\LSAXProbe\ (README-PROBES.md section 3/7/10).
$script:RunFilePatterns = @('probe-*.log', 'sqlite-probe.log', 'probe-ledger.tsv', 'session-token.txt', 'domains-*.count')
# Probe-owned SQLite files (P-DB-01). Moved by NEW-RUN, never collected (not evidence), deleted only on request.
$script:RunDbPatterns = @('p0.db', 'p0.db-wal', 'p0.db-shm', 'p0_proj.db', 'p0_proj.db-wal', 'p0_proj.db-shm',
    'p0_snap.db', 'p0_journal_backup.db')
$script:GameProcessNames = @('GTA5', 'GTA5_Enhanced', 'PlayGTAV', 'GTAVLauncher')

function Write-Lsax([string]$Message) {
    Write-Host ('[LSAX] ' + $Message)
}

function Write-LsaxWarn([string]$Message) {
    Write-Host ('[LSAX-WARN] ' + $Message) -ForegroundColor Yellow
}

function Exit-Lsax([int]$Code, [string]$Message) {
    if ($Code -eq 0) {
        Write-Host ('[LSAX-OK] ' + $Message) -ForegroundColor Green
    }
    else {
        Write-Host ('[LSAX-FAILED] ' + $Message + ' (exit code ' + $Code + ')') -ForegroundColor Red
    }
    exit $Code
}

function Get-PackRoot {
    # scripts\lib\<this file> -> pack root
    return (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}

function Join-Rel([string]$Base, [string]$Rel) {
    $p = $Base
    foreach ($part in ($Rel -split '[\\/]')) {
        if ($part.Length -gt 0) {
            $p = Join-Path $p $part
        }
    }
    return $p
}

function Get-RelPath([string]$Base, [string]$Full) {
    $b = [System.IO.Path]::GetFullPath($Base).TrimEnd('\', '/')
    $f = [System.IO.Path]::GetFullPath($Full)
    if (-not $f.StartsWith($b, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw ('path is outside the base folder: ' + $Full)
    }
    return ($f.Substring($b.Length).TrimStart('\', '/') -replace '\\', '/')
}

function Test-Inside([string]$Base, [string]$Full) {
    $b = [System.IO.Path]::GetFullPath($Base).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $f = [System.IO.Path]::GetFullPath($Full)
    return $f.StartsWith($b, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-UtcStamp {
    return [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-SharedBytes([string]$Path) {
    # Opens with FileShare.ReadWrite|Delete so a probe that appends to its log at the same moment never gets a
    # sharing violation (the probes silently drop a log line on IOException).
    $fs = New-Object System.IO.FileStream($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
        ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try {
        $ms = New-Object System.IO.MemoryStream
        $fs.CopyTo($ms)
        return , $ms.ToArray()
    }
    finally {
        $fs.Dispose()
    }
}

function Read-SharedLines([string]$Path) {
    $bytes = Read-SharedBytes $Path
    $text = (New-Object System.Text.UTF8Encoding($false)).GetString($bytes)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    return , ($text -split "`r?`n")
}

function Write-TextFile([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $script:Utf8NoBom)
}

function Read-Confirm([string]$Prompt, [string]$Expected, [bool]$AssumeYes) {
    if ($AssumeYes) {
        Write-Lsax ($Prompt + ' -> assumed "' + $Expected + '" (-AssumeYes)')
        return $true
    }
    $answer = Read-Host ($Prompt + ' Type ' + $Expected + ' to continue, anything else aborts')
    return ($answer -ceq $Expected)
}

function Assert-GameNotRunning {
    foreach ($n in $script:GameProcessNames) {
        $p = Get-Process -Name $n -ErrorAction SilentlyContinue
        if ($p) {
            Exit-Lsax 3 ('GTA V is running (process ' + $n + '). Close the game completely and run this again.')
        }
    }
}

function Resolve-GtaRoot([string]$GtaRoot) {
    if ([string]::IsNullOrWhiteSpace($GtaRoot)) {
        Write-Lsax 'The GTA V Legacy folder is required (the folder that contains GTA5.exe).'
        Write-Lsax 'This script never guesses it. Example: D:\Games\Grand Theft Auto V'
        $GtaRoot = Read-Host 'Full path of your GTA V Legacy folder'
    }
    if ($null -eq $GtaRoot) {
        # Read-Host returns $null when the input stream is closed (e.g. Ctrl+Z or redirected input)
        $GtaRoot = ''
    }
    $GtaRoot = $GtaRoot.Trim().Trim('"').TrimEnd('\', '/')
    if ([string]::IsNullOrWhiteSpace($GtaRoot)) {
        Exit-Lsax 1 'No GTA folder given.'
    }
    if (-not (Test-Path -LiteralPath $GtaRoot -PathType Container)) {
        Exit-Lsax 1 ('Folder does not exist: ' + $GtaRoot)
    }
    $GtaRoot = [System.IO.Path]::GetFullPath($GtaRoot)
    $legacy = Join-Path $GtaRoot 'GTA5.exe'
    $enhanced = Join-Path $GtaRoot 'GTA5_Enhanced.exe'
    if (-not (Test-Path -LiteralPath $legacy -PathType Leaf)) {
        if (Test-Path -LiteralPath $enhanced -PathType Leaf) {
            Exit-Lsax 1 ('Only GTA5_Enhanced.exe found. The Phase 0 target runtime is GTA V LEGACY 1.0.3725.0: ' + $GtaRoot)
        }
        Exit-Lsax 1 ('GTA5.exe not found in ' + $GtaRoot + ' - give the folder that contains GTA5.exe.')
    }
    foreach ($req in @('ScriptHookV.dll', 'ScriptHookVDotNet.asi')) {
        if (-not (Test-Path -LiteralPath (Join-Path $GtaRoot $req) -PathType Leaf)) {
            Exit-Lsax 1 ($req + ' not found in the GTA folder. Install ScriptHookV and ScriptHookVDotNet 3.7.x first (the pack never installs them).')
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $GtaRoot 'ScriptHookVDotNet3.dll') -PathType Leaf)) {
        Write-LsaxWarn 'ScriptHookVDotNet3.dll not found in the GTA folder; the probes need the SHVDN v3 API.'
    }
    return $GtaRoot
}

function Read-ShvdnIni([string]$GtaRoot) {
    # READ ONLY. SHVDN reads <GTA>\ScriptHookVDotNet.ini (DllMain.cpp: ChangeExtension(asi location, ".ini")).
    $r = @{ Present = $false; ScriptsLocation = $null; AutoLoadScripts = $null; ConsoleKeyBinding = $null; ReloadKeyBinding = $null }
    $ini = Join-Path $GtaRoot 'ScriptHookVDotNet.ini'
    if (-not (Test-Path -LiteralPath $ini -PathType Leaf)) {
        return $r
    }
    $r.Present = $true
    foreach ($raw in [System.IO.File]::ReadAllLines($ini)) {
        $line = $raw.Trim()
        $eq = $line.IndexOf('=')
        if ($line.Length -eq 0 -or $line.StartsWith(';') -or $line.StartsWith('[') -or $eq -le 0) {
            continue
        }
        $k = $line.Substring(0, $eq).Trim()
        $v = $line.Substring($eq + 1).Trim()
        foreach ($name in @('ScriptsLocation', 'AutoLoadScripts', 'ConsoleKeyBinding', 'ReloadKeyBinding')) {
            if ($k -ieq $name) {
                $r[$name] = $v
            }
        }
    }
    return $r
}

function Resolve-ScriptsDir([string]$GtaRoot, [bool]$AssumeYes) {
    $ini = Read-ShvdnIni $GtaRoot
    $loc = 'scripts'
    if ($ini.ScriptsLocation) {
        $loc = $ini.ScriptsLocation.Trim('"')
    }
    if ($ini.AutoLoadScripts -and ($ini.AutoLoadScripts -ieq 'false')) {
        Exit-Lsax 1 'ScriptHookVDotNet.ini has AutoLoadScripts=false. The validation procedure needs auto-loading. Change it yourself (this pack never edits SHVDN files) and run again.'
    }
    if ([System.IO.Path]::IsPathRooted($loc)) {
        $dir = $loc
    }
    else {
        # SHVDN resolves a relative ScriptsLocation against the game's working directory (normally the GTA folder).
        $dir = Join-Rel $GtaRoot $loc
    }
    $dir = [System.IO.Path]::GetFullPath($dir)
    if (-not ($loc -ieq 'scripts')) {
        Write-LsaxWarn ('ScriptHookVDotNet.ini sets ScriptsLocation=' + $ini.ScriptsLocation + ' -> ' + $dir)
        if (-not (Read-Confirm 'Use this SHVDN scripts folder?' 'YES' $AssumeYes)) {
            Exit-Lsax 4 'Aborted by the owner.'
        }
    }
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
        Exit-Lsax 1 ('SHVDN scripts folder does not exist: ' + $dir + ' - create it only if SHVDN is installed correctly.')
    }
    return $dir
}

function Read-DeploymentManifest([string]$PackRoot) {
    $path = Join-Rel $PackRoot 'install/DEPLOYMENT-MANIFEST.tsv'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Exit-Lsax 2 ('Pack file missing: install/DEPLOYMENT-MANIFEST.tsv')
    }
    $rows = @()
    foreach ($line in [System.IO.File]::ReadAllLines($path)) {
        if ($line.Length -eq 0 -or $line.StartsWith('#') -or $line.StartsWith('component')) {
            continue
        }
        $f = $line.Split("`t")
        if ($f.Length -ne 4) {
            Exit-Lsax 2 ('Malformed DEPLOYMENT-MANIFEST.tsv line: ' + $line)
        }
        $rows += New-Object PSObject -Property @{ Component = $f[0]; Source = $f[1]; Dest = $f[2]; Sha256 = $f[3].ToLowerInvariant() }
    }
    return $rows
}

function Assert-OwnDest([string]$Dest) {
    # Every destination of this pack is one of: LsaxPhase0Probe.dll, LSAXProbeSql/<file>, LSAXProbe/<file>.
    $d = $Dest -replace '\\', '/'
    if ($d.Contains('..') -or $d.StartsWith('/')) {
        throw ('refusing unsafe destination ' + $Dest)
    }
    if ($d -ieq 'LsaxPhase0Probe.dll') {
        return
    }
    if ($d -match '^(LSAXProbeSql|LSAXProbe)/[^/]+$' -or $d -match '^LSAXProbe/install-backup/') {
        return
    }
    throw ('refusing destination outside the pack folders: ' + $Dest)
}

function Get-InstallManifestPath([string]$ScriptsDir) {
    return (Join-Rel $ScriptsDir ($script:ProbeDirName + '/' + $script:ManifestName))
}

function Read-InstallManifest([string]$ScriptsDir) {
    $path = Get-InstallManifestPath $ScriptsDir
    $map = [ordered]@{}
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $map
    }
    foreach ($line in [System.IO.File]::ReadAllLines($path)) {
        if ($line.Length -eq 0 -or $line.StartsWith('#') -or $line.StartsWith('dest_rel')) {
            continue
        }
        $f = $line.Split("`t")
        if ($f.Length -lt 5) {
            continue
        }
        Assert-OwnDest $f[0]
        $map[$f[0]] = New-Object PSObject -Property @{ Dest = $f[0]; Sha256 = $f[1]; Component = $f[2]; Backup = $f[3]; InstalledUtc = $f[4] }
    }
    return $map
}

function Write-InstallManifest([string]$ScriptsDir, $Map) {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("# $($script:LsaxPackName) install manifest v1 - files installed by the pack (paths relative to the SHVDN scripts folder)`r`n")
    [void]$sb.Append("# REMOVE-PROBES.cmd deletes exactly these paths (and only while their SHA-256 still matches). Do not edit.`r`n")
    [void]$sb.Append("dest_rel`tsha256`tcomponent`tbackup_rel`tinstalled_utc`r`n")
    foreach ($k in $Map.Keys) {
        $e = $Map[$k]
        [void]$sb.Append($e.Dest + "`t" + $e.Sha256 + "`t" + $e.Component + "`t" + $e.Backup + "`t" + $e.InstalledUtc + "`r`n")
    }
    Write-TextFile (Get-InstallManifestPath $ScriptsDir) $sb.ToString()
}

function Get-ProfileText([string]$PackRoot, [string]$ProfileName, [string]$ScriptsDir) {
    if ($script:ProfileNames -notcontains $ProfileName) {
        Exit-Lsax 1 ('Unknown profile ' + $ProfileName + '. Allowed: ' + ($script:ProfileNames -join ', '))
    }
    $src = Join-Rel $PackRoot ('install/config/probe.' + $ProfileName + '.ini')
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        Exit-Lsax 2 ('Pack file missing: install/config/probe.' + $ProfileName + '.ini')
    }
    $text = [System.IO.File]::ReadAllText($src)
    # P-SL-02 is never enabled by a script (optional, disposable save only, manual consent - 08-P-SL-02-OPTIONAL-RU.md).
    if ($text -match '(?im)^\s*AnchorProbe\.Enabled\s*=\s*true') {
        Exit-Lsax 2 'Refusing a profile that enables AnchorProbe (P-SL-02).'
    }
    $native = Join-Rel $ScriptsDir ($script:SqlDirName + '/e_sqlite3.dll')
    return $text.Replace('@@SQLITE_NATIVE_PATH@@', $native)
}

function Get-TextSha256([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $script:Utf8NoBom.GetBytes($Text)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Backup-OwnFile([string]$ScriptsDir, [string]$DestRel, [string]$Stamp) {
    # Backups live inside our own folder and end in .lsaxbak so SHVDN (which loads *.dll, *.cs, *.vb recursively)
    # never loads them.
    $src = Join-Rel $ScriptsDir $DestRel
    $stem = $script:ProbeDirName + '/install-backup/' + $Stamp + '/' + ($DestRel -replace '[\\/]', '__')
    $bakRel = $stem + '.lsaxbak'
    $n = 2
    while (Test-Path -LiteralPath (Join-Rel $ScriptsDir $bakRel)) {
        # never overwrite an earlier backup
        $bakRel = $stem + '-' + $n + '.lsaxbak'
        $n++
    }
    Assert-OwnDest $bakRel
    $bak = Join-Rel $ScriptsDir $bakRel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bak) | Out-Null
    Copy-Item -LiteralPath $src -Destination $bak -Force
    if ((Get-Sha256 $src) -ne (Get-Sha256 $bak)) {
        throw ('backup verification failed for ' + $DestRel)
    }
    Write-Lsax ('  backed up existing ' + $DestRel + ' -> ' + $bakRel)
    return $bakRel
}

function Get-EvidenceWorkDir([string]$PackRoot, [string]$Config) {
    if ($script:ConfigNames -notcontains $Config) {
        Exit-Lsax 1 ('-Config must be one of: ' + ($script:ConfigNames -join ', '))
    }
    return (Join-Rel $PackRoot ('evidence-work/' + $Config))
}

function Get-RunFiles([string]$Dir, [bool]$IncludeDb) {
    $out = @()
    if (-not (Test-Path -LiteralPath $Dir -PathType Container)) {
        return $out
    }
    $patterns = $script:RunFilePatterns
    if ($IncludeDb) {
        $patterns = $patterns + $script:RunDbPatterns
    }
    foreach ($pat in $patterns) {
        foreach ($f in (Get-ChildItem -LiteralPath $Dir -File -Filter $pat -ErrorAction SilentlyContinue)) {
            # -Filter uses Win32 matching (8.3 short-name quirks); -like re-checks the exact long name.
            if (($f.Name -like $pat) -and ($out -notcontains $f.FullName)) {
                $out += $f.FullName
            }
        }
    }
    return ($out | Sort-Object)
}
