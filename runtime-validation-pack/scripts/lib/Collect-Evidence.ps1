# =====================================================================================
# COLLECT-EVIDENCE - packs ONLY the LSAX Phase 0 validation evidence into
#   <OutDir>\LSAX-PHASE0-RUNTIME-EVIDENCE-YYYYMMDD-HHMM.zip   (default OutDir = <pack>\evidence-out)
# NOT LSAX PRODUCTION CODE.
# Collected (and nothing else):
#   <scripts>\LSAXProbe\ and <scripts>\LSAXProbe\runs\*\ : probe-*.log, sqlite-probe.log, probe-ledger.tsv,
#       session-token.txt, domains-*.count
#   <scripts>\LSAXProbe\ : probe.ini, LSAX-PACK-INSTALL-MANIFEST.tsv, install-report-*.txt
#   SHA-256 of the installed LsaxPhase0Probe.dll / LsaxPhase0SqliteProbe.dll
#   <pack>\evidence-work\<Config>\ : ENVIRONMENT.txt, TEST-LOG.tsv, smoke-state.txt, check-log-output.txt, NOTES*.txt
#   <pack>\SHA256SUMS.txt, PACK-INFO.txt, install\DEPLOYMENT-MANIFEST.tsv (package manifest)
#   AUTO-DETECTED.txt: file versions of GTA5.exe / ScriptHookV / SHVDN, Windows and .NET versions (no names, no paths)
#   optional (-IncludeShvdnLogExcerpt): only the lines of ScriptHookVDotNet.log that mention the probes or SQLite
# Never collected: saves, the GTA installation, other scripts or mods, other logs, screenshots, personal files.
# Text is redacted: the GTA folder, the scripts folder, Documents, the user profile and any C:\Users\<name>
# path are replaced by placeholders; REDACTION.txt lists every file, its original SHA-256 and the counts.
# Exit codes: 0 ok, 1 invalid input, 3 game running, 6 nothing to collect, 7 zip failed.
# =====================================================================================
param(
    [string]$GtaRoot,
    [Parameter(Mandatory = $true)][string]$Config,
    [ValidateSet('SMOKE', 'FULL', 'PDB01', 'PID01', 'PSL02', 'OTHER')][string]$Phase = 'FULL',
    [string]$OutDir,
    [switch]$IncludeShvdnLogExcerpt
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

Write-Lsax ($script:LsaxPackName + ' - COLLECT-EVIDENCE config=' + $Config + ' phase=' + $Phase)
Assert-GameNotRunning
$pack = Get-PackRoot
$work = Get-EvidenceWorkDir $pack $Config
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $false
$probeDir = Join-Path $scripts $script:ProbeDirName
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $pack 'evidence-out'
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = [System.IO.Path]::GetFullPath($OutDir)

$localStamp = (Get-Date).ToString('yyyyMMdd-HHmm', [System.Globalization.CultureInfo]::InvariantCulture)
$baseName = 'LSAX-PHASE0-RUNTIME-EVIDENCE-' + $localStamp
$zipPath = Join-Path $OutDir ($baseName + '.zip')
$k = 2
while (Test-Path -LiteralPath $zipPath) {
    $zipPath = Join-Path $OutDir ($baseName + '-' + $k + '.zip')
    $k++
}
$rootName = [System.IO.Path]::GetFileNameWithoutExtension($zipPath)
$stage = Join-Path $OutDir ('_staging-' + (Get-UtcStamp) + '-' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))
$stageRoot = Join-Path $stage $rootName
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

# ---------------------------------------------------------------- redaction
$docs = [Environment]::GetFolderPath('MyDocuments')
$repl = New-Object System.Collections.ArrayList
foreach ($pair in @(@($scripts, '<SCRIPTS>'), @($gta, '<GTA>'), @($docs, '<DOCUMENTS>'), @($env:USERPROFILE, '<USERPROFILE>'), @($env:HOME, '<HOME>'))) {
    if (-not [string]::IsNullOrWhiteSpace($pair[0]) -and $pair[0].Length -ge 4) {
        [void]$repl.Add($pair)
    }
}
$redactionLog = New-Object System.Collections.ArrayList
[void]$redactionLog.Add("file`toriginal_sha256`treplacements`tdecoded_as")
$script:LastDecode = ''
function Read-AnyText([string]$Path) {
    # Probe logs are UTF-8. Owner files may be UTF-8, UTF-16 (Excel "Unicode text") or ANSI (old Notepad).
    $b = Read-SharedBytes $Path
    if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) {
        $script:LastDecode = 'utf-16le'
        return [System.Text.Encoding]::Unicode.GetString($b, 2, $b.Length - 2)
    }
    if ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) {
        $script:LastDecode = 'utf-16be'
        return [System.Text.Encoding]::BigEndianUnicode.GetString($b, 2, $b.Length - 2)
    }
    $start = 0
    if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
        $start = 3
    }
    try {
        $script:LastDecode = 'utf-8'
        return (New-Object System.Text.UTF8Encoding($false, $true)).GetString($b, $start, $b.Length - $start)
    }
    catch {
        $script:LastDecode = 'ansi-' + [System.Text.Encoding]::Default.WebName
        return [System.Text.Encoding]::Default.GetString($b)
    }
}
function Copy-Redacted([string]$Src, [string]$DestRel) {
    $dest = Join-Rel $stageRoot $DestRel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    $orig = Get-Sha256 $Src
    $text = Read-AnyText $Src
    $count = 0
    foreach ($pair in $repl) {
        $rx = [regex]::Escape($pair[0].TrimEnd('\', '/'))
        $m = [regex]::Matches($text, $rx, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($m.Count -gt 0) {
            $count += $m.Count
            $text = [regex]::Replace($text, $rx, $pair[1], [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        }
    }
    $rxUser = '([A-Za-z]:\\Users\\)[^\\\t\r\n\]]+'
    $m = [regex]::Matches($text, $rxUser)
    if ($m.Count -gt 0) {
        $count += $m.Count
        $text = [regex]::Replace($text, $rxUser, '$1<USER>')
    }
    Write-TextFile $dest $text
    [void]$redactionLog.Add($DestRel + "`t" + $orig + "`t" + $count + "`t" + $script:LastDecode)
}

# ---------------------------------------------------------------- probe run files
$collected = 0
if (Test-Path -LiteralPath $probeDir -PathType Container) {
    foreach ($f in @(Get-RunFiles $probeDir $false)) {
        Copy-Redacted $f ('probe-run/current/' + (Split-Path -Leaf $f))
        $collected++
    }
    $runsDir = Join-Path $probeDir 'runs'
    if (Test-Path -LiteralPath $runsDir -PathType Container) {
        foreach ($d in (Get-ChildItem -LiteralPath $runsDir -Directory | Sort-Object Name)) {
            foreach ($f in @(Get-RunFiles $d.FullName $false)) {
                Copy-Redacted $f ('probe-run/runs/' + $d.Name + '/' + (Split-Path -Leaf $f))
                $collected++
            }
        }
    }
    foreach ($name in @('probe.ini', $script:ManifestName)) {
        $p = Join-Path $probeDir $name
        if (Test-Path -LiteralPath $p -PathType Leaf) {
            Copy-Redacted $p ('probe-bookkeeping/' + $name)
        }
    }
    foreach ($f in (Get-ChildItem -LiteralPath $probeDir -File -Filter 'install-report-*.txt' -ErrorAction SilentlyContinue)) {
        if ($f.Name -like 'install-report-*.txt') {
            Copy-Redacted $f.FullName ('probe-bookkeeping/' + $f.Name)
        }
    }
}
if ($collected -eq 0) {
    Write-LsaxWarn 'No probe log files found in <scripts>\LSAXProbe. The evidence ZIP will contain only the environment files.'
}

# ---------------------------------------------------------------- probe DLL hashes
$manifest = Read-InstallManifest $scripts
$sb = New-Object System.Text.StringBuilder
[void]$sb.Append("installed_file`tsha256_now`tsha256_install_manifest`r`n")
foreach ($rel in @('LsaxPhase0Probe.dll', ($script:SqlDirName + '/LsaxPhase0SqliteProbe.dll'))) {
    $p = Join-Rel $scripts $rel
    $now = '<absent>'
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        $now = Get-Sha256 $p
    }
    $man = '<not in manifest>'
    if ($manifest.Contains($rel)) {
        $man = $manifest[$rel].Sha256
    }
    [void]$sb.Append($rel + "`t" + $now + "`t" + $man + "`r`n")
}
Write-TextFile (Join-Path $stageRoot 'PROBE-DLL-SHA256.txt') $sb.ToString()

# ---------------------------------------------------------------- owner files
$ownerNames = @('ENVIRONMENT.txt', 'TEST-LOG.tsv', 'smoke-state.txt', 'check-log-output.txt')
if (Test-Path -LiteralPath $work -PathType Container) {
    foreach ($f in (Get-ChildItem -LiteralPath $work -File)) {
        if (($ownerNames -contains $f.Name) -or ($f.Name -like 'NOTES*.txt')) {
            if ($f.Length -gt 5MB) {
                Write-LsaxWarn ('Skipped (larger than 5 MB): ' + $f.Name)
                continue
            }
            Copy-Redacted $f.FullName ('owner/' + $f.Name)
        }
    }
}
foreach ($must in @('ENVIRONMENT.txt', 'TEST-LOG.tsv')) {
    if (-not (Test-Path -LiteralPath (Join-Path $work $must) -PathType Leaf)) {
        Write-LsaxWarn ('evidence-work\' + $Config + '\' + $must + ' is missing - run PREPARE-EVIDENCE-FOLDER.cmd and fill it in; the reviewer needs it.')
    }
}

# ---------------------------------------------------------------- package manifest
foreach ($rel in @('SHA256SUMS.txt', 'PACK-INFO.txt', 'install/DEPLOYMENT-MANIFEST.tsv')) {
    $p = Join-Rel $pack $rel
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        $dest = Join-Rel $stageRoot ('pack/' + (Split-Path -Leaf $p))
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $p -Destination $dest
    }
}

# ---------------------------------------------------------------- auto-detected versions (no names, no paths)
function FileVer([string]$Rel) {
    $p = Join-Path $gta $Rel
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        return '<absent>'
    }
    try {
        $vi = (Get-Item -LiteralPath $p).VersionInfo
        return ('FileVersion=' + $vi.FileVersion + ' ProductVersion=' + $vi.ProductVersion)
    }
    catch {
        return '<unreadable>'
    }
}
$ad = New-Object System.Text.StringBuilder
[void]$ad.Append("# Auto-detected by COLLECT-EVIDENCE (informative). The owner's ENVIRONMENT.txt is authoritative.`r`n")
[void]$ad.Append("collect_local_time`t" + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + "`r`n")
[void]$ad.Append("config`t$Config`r`nphase`t$Phase`r`n")
foreach ($f in @('GTA5.exe', 'GTA5_Enhanced.exe', 'ScriptHookV.dll', 'ScriptHookVDotNet.asi', 'ScriptHookVDotNet3.dll', 'ScriptHookVDotNet2.dll', 'dinput8.dll')) {
    [void]$ad.Append($f + "`t" + (FileVer $f) + "`r`n")
}
$ini = Read-ShvdnIni $gta
[void]$ad.Append("ScriptHookVDotNet.ini`tpresent=" + $ini.Present + " ScriptsLocation=" + $(if ($ini.ScriptsLocation) { 'custom' } else { 'default' }) + " AutoLoadScripts=" + $ini.AutoLoadScripts + " ConsoleKeyBinding=" + $ini.ConsoleKeyBinding + " ReloadKeyBinding=" + $ini.ReloadKeyBinding + "`r`n")
if ($script:OnWindows) {
    try {
        $cv = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
        $vals = @{}
        foreach ($n in @('ProductName', 'DisplayVersion', 'CurrentBuild', 'UBR')) {
            # StrictMode: read only properties that exist (DisplayVersion/UBR are absent on older Windows builds)
            $vals[$n] = ''
            if ($cv.PSObject.Properties[$n]) {
                $vals[$n] = [string]$cv.PSObject.Properties[$n].Value
            }
        }
        [void]$ad.Append("windows`t" + $vals.ProductName + ' ' + $vals.DisplayVersion + ' build ' + $vals.CurrentBuild + '.' + $vals.UBR + "`r`n")
    }
    catch {
        [void]$ad.Append("windows`t<unreadable>`r`n")
    }
    try {
        $nf = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full'
        [void]$ad.Append("dotnet_framework_release`t" + $nf.Release + "`r`n")
    }
    catch {
        [void]$ad.Append("dotnet_framework_release`t<unreadable>`r`n")
    }
}
else {
    [void]$ad.Append("windows`t<not Windows: " + [System.Environment]::OSVersion.VersionString + ">`r`n")
}
[void]$ad.Append("powershell`t" + $PSVersionTable.PSVersion.ToString() + "`r`n")
Write-TextFile (Join-Path $stageRoot 'AUTO-DETECTED.txt') $ad.ToString()

# ---------------------------------------------------------------- optional SHVDN log excerpt
if ($IncludeShvdnLogExcerpt) {
    $shvdnLog = Join-Path $gta 'ScriptHookVDotNet.log'
    if (Test-Path -LiteralPath $shvdnLog -PathType Leaf) {
        $tmp = Join-Path $stage 'shvdn-excerpt.tmp'
        $lines = @([System.IO.File]::ReadAllLines($shvdnLog) | Where-Object { $_ -match '(?i)LsaxPhase0|LSAXProbe|sqlite|SQLitePCL|System\.Memory|System\.Buffers|System\.Numerics\.Vectors|CompilerServices\.Unsafe' })
        Write-TextFile $tmp (($lines -join "`r`n") + "`r`n")
        Copy-Redacted $tmp 'shvdn-log-excerpt.txt'
        Remove-Item -LiteralPath $tmp
    }
    else {
        Write-LsaxWarn 'ScriptHookVDotNet.log not found next to ScriptHookVDotNet.asi - excerpt skipped.'
    }
}

# ---------------------------------------------------------------- info, redaction list, checksums
$info = "$($script:LsaxPackName) evidence`r`n" +
"config`t$Config`r`nphase`t$Phase`r`nprobe_run_files`t$collected`r`n" +
"labels`tEvidence produced by the OWNER on the owner's PC. Claude prepared the pack offline and never ran it. PASS/FAIL is decided only by the independent reviewer.`r`n" +
"redaction`tpaths replaced by <SCRIPTS>, <GTA>, <DOCUMENTS>, <USERPROFILE>, <HOME>, C:\Users\<USER>; see REDACTION.txt (original SHA-256 per file). No other change.`r`n"
Write-TextFile (Join-Path $stageRoot 'COLLECT-INFO.txt') $info
Write-TextFile (Join-Path $stageRoot 'REDACTION.txt') (($redactionLog -join "`r`n") + "`r`n")
$sums = New-Object System.Text.StringBuilder
foreach ($f in (Get-ChildItem -LiteralPath $stageRoot -Recurse -File | Sort-Object FullName)) {
    [void]$sums.Append((Get-Sha256 $f.FullName) + '  ' + (Get-RelPath $stageRoot $f.FullName) + "`r`n")
}
Write-TextFile (Join-Path $stageRoot 'EVIDENCE-SHA256SUMS.txt') $sums.ToString()

# ---------------------------------------------------------------- zip (ZipArchive with '/' entry names; Compress-Archive fallback)
$files = @(Get-ChildItem -LiteralPath $stageRoot -Recurse -File | Sort-Object FullName)
$zipOk = $false
try {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $fs = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::CreateNew)
    try {
        $za = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($f in $files) {
                $name = $rootName + '/' + (Get-RelPath $stageRoot $f.FullName)
                [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($za, $f.FullName, $name, [System.IO.Compression.CompressionLevel]::Optimal)
            }
        }
        finally {
            $za.Dispose()
        }
    }
    finally {
        $fs.Dispose()
    }
    $zipOk = $true
}
catch {
    Write-LsaxWarn ('ZipArchive failed (' + $_.Exception.Message + '); using Compress-Archive fallback.')
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath
    }
    try {
        Compress-Archive -LiteralPath $stageRoot -DestinationPath $zipPath
        $zipOk = $true
    }
    catch {
        Write-LsaxWarn ('Compress-Archive failed: ' + $_.Exception.Message)
    }
}
if (-not $zipOk) {
    Exit-Lsax 7 ('Could not create the ZIP. The collected files are in ' + $stageRoot + ' - zip that folder by hand.')
}

# verify: every staged file is in the zip
Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
$zr = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$entryCount = $zr.Entries.Count
$zr.Dispose()
if ($entryCount -lt $files.Count) {
    Exit-Lsax 7 ('ZIP has ' + $entryCount + ' entries, expected ' + $files.Count + '. Staged files kept in ' + $stageRoot)
}
Remove-Item -LiteralPath $stage -Recurse -Force
Write-Lsax ('Evidence ZIP : ' + $zipPath)
Write-Lsax ('Entries      : ' + $entryCount)
Write-Lsax ('SHA-256      : ' + (Get-Sha256 $zipPath))
Write-Lsax 'Open the ZIP once and check it contains nothing personal before sending it to the independent reviewer.'
Exit-Lsax 0 'Evidence collected. Nothing in it is a PASS: the independent reviewer decides.'
