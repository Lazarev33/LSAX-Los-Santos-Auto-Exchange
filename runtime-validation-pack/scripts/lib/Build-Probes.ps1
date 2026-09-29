# =====================================================================================
# BUILD-PROBES-WINDOWS - optional local rebuild of the two probe projects from source\ on the owner's PC.
# NOT LSAX PRODUCTION CODE. Needs the .NET SDK 8 or newer and internet access to nuget.org.
# Works on a copy: build-local\<UTC>\src ; outputs are copied to build-local\main and build-local\sql,
# where INSTALL-PROBES.cmd -UseLocalBuild picks them up. The pack's own payload (install\) is never changed.
# Byte equality with install\ is expected only with the same SDK/compiler (see install\BUILD-INFO.txt);
# a DIFFERENT result is reported, not treated as an error.
# Exit codes: 0 built, 9 build failed / SDK missing / output incomplete.
# =====================================================================================
param()

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

Write-Lsax ($script:LsaxPackName + ' - BUILD-PROBES-WINDOWS (optional)')
$pack = Get-PackRoot
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet) {
    Exit-Lsax 9 'dotnet not found. Install the .NET SDK 8 (x64) or skip this step and use the prebuilt payload in install\.'
}
$ver = (& dotnet --version).Trim()
Write-Lsax ('dotnet SDK: ' + $ver)
$major = 0
[void][int]::TryParse(($ver -split '\.')[0], [ref]$major)
if ($major -lt 8) {
    Exit-Lsax 9 ('.NET SDK 8 or newer required, found ' + $ver)
}

$stamp = Get-UtcStamp
$root = Join-Rel $pack ('build-local/' + $stamp)
$src = Join-Path $root 'src'
New-Item -ItemType Directory -Force -Path $src | Out-Null
Copy-Item -LiteralPath (Join-Rel $pack 'source/LsaxPhase0Probe') -Destination $src -Recurse
Copy-Item -LiteralPath (Join-Rel $pack 'source/LsaxPhase0SqliteProbe') -Destination $src -Recurse
$outMain = Join-Path $root 'main'
$outSql = Join-Path $root 'sql'

$common = @('-c', 'Release', '-p:DebugType=none', '-p:ContinuousIntegrationBuild=true', '-p:IncludeSourceRevisionInInformationalVersion=false', '-nologo')
& dotnet build (Join-Rel $src 'LsaxPhase0Probe/LsaxPhase0Probe.csproj') @common -o $outMain
if ($LASTEXITCODE -ne 0) {
    Exit-Lsax 9 'LsaxPhase0Probe build failed (see the output above).'
}
& dotnet build (Join-Rel $src 'LsaxPhase0SqliteProbe/LsaxPhase0SqliteProbe.csproj') @common '-p:RuntimeIdentifier=win-x64' -o $outSql
if ($LASTEXITCODE -ne 0) {
    Exit-Lsax 9 'LsaxPhase0SqliteProbe build failed (see the output above).'
}

$rows = @(Read-DeploymentManifest $pack)
$rep = New-Object System.Text.StringBuilder
[void]$rep.Append("local build $stamp UTC, dotnet SDK $ver`r`nfile`tlocal_sha256`tpack_sha256`tcompare`r`n")
$missing = 0
foreach ($dir in @('main', 'sql')) {
    New-Item -ItemType Directory -Force -Path (Join-Rel $pack ('build-local/' + $dir)) | Out-Null
}
foreach ($r in $rows) {
    $name = Split-Path -Leaf $r.Source
    $from = Join-Path $root (Join-Path $r.Component $name)
    if (-not (Test-Path -LiteralPath $from -PathType Leaf)) {
        Write-LsaxWarn ('missing in local output: ' + $r.Component + '/' + $name)
        $missing++
        continue
    }
    Copy-Item -LiteralPath $from -Destination (Join-Rel $pack ('build-local/' + $r.Component + '/' + $name)) -Force
    $h = Get-Sha256 $from
    $cmp = 'DIFFERENT'
    if ($h -eq $r.Sha256) {
        $cmp = 'MATCH'
    }
    Write-Lsax ('  ' + $cmp + '  ' + $r.Component + '/' + $name)
    [void]$rep.Append($r.Component + '/' + $name + "`t" + $h + "`t" + $r.Sha256 + "`t" + $cmp + "`r`n")
}
Write-TextFile (Join-Rel $pack 'build-local/BUILD-LOCAL-REPORT.txt') $rep.ToString()
if ($missing -gt 0) {
    Exit-Lsax 9 ($missing.ToString() + ' expected file(s) missing from the local build output.')
}
Exit-Lsax 0 'Local build done: build-local\main and build-local\sql. Use INSTALL-PROBES.cmd -UseLocalBuild to install it (optional).'
