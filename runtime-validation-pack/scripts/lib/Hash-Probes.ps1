# =====================================================================================
# HASH-PROBES - read-only integrity check.
# NOT LSAX PRODUCTION CODE.
#   (no arguments) or -VerifyPack : checks every line of the pack's SHA256SUMS.txt against the extracted files.
#   -GtaRoot <path>               : checks every installed probe file against the install manifest and prints
#                                   the SHA-256 of both probe DLLs (for ENVIRONMENT.txt).
# Writes nothing. Exit codes: 0 all match, 2 mismatch/missing, 6 probes not installed, 1 invalid input.
# =====================================================================================
param(
    [switch]$VerifyPack,
    [string]$GtaRoot
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

$pack = Get-PackRoot
$doPack = $VerifyPack -or [string]::IsNullOrWhiteSpace($GtaRoot)
$bad = 0

if ($doPack) {
    Write-Lsax ('Verifying the extracted pack against SHA256SUMS.txt: ' + $pack)
    $sums = Join-Path $pack 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $sums -PathType Leaf)) {
        Exit-Lsax 2 'SHA256SUMS.txt missing - re-extract the pack.'
    }
    $n = 0
    foreach ($line in [System.IO.File]::ReadAllLines($sums)) {
        if ($line.Length -eq 0 -or $line.StartsWith('#')) {
            continue
        }
        $h = $line.Substring(0, 64).ToLowerInvariant()
        $rel = $line.Substring(66)
        $p = Join-Rel $pack $rel
        $n++
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
            Write-LsaxWarn ('MISSING  ' + $rel)
            $bad++
        }
        elseif ((Get-Sha256 $p) -ne $h) {
            Write-LsaxWarn ('CHANGED  ' + $rel)
            $bad++
        }
    }
    Write-Lsax ('pack files checked: ' + $n + ', problems: ' + $bad)
}

if (-not [string]::IsNullOrWhiteSpace($GtaRoot)) {
    $gta = Resolve-GtaRoot $GtaRoot
    $scripts = Resolve-ScriptsDir $gta $false
    $manifest = Read-InstallManifest $scripts
    if ($manifest.Count -eq 0) {
        Exit-Lsax 6 'No install manifest in <scripts>\LSAXProbe - the probes are not installed by this pack here.'
    }
    Write-Lsax 'Installed probe files (install manifest):'
    foreach ($k in $manifest.Keys) {
        $e = $manifest[$k]
        $p = Join-Rel $scripts $e.Dest
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
            Write-LsaxWarn ('MISSING  ' + $e.Dest)
            $bad++
            continue
        }
        $h = Get-Sha256 $p
        if ($h -ne $e.Sha256) {
            Write-LsaxWarn ('CHANGED  ' + $e.Dest + '  now ' + $h)
            $bad++
        }
        else {
            Write-Lsax ('  ok  ' + $h + '  ' + $e.Dest)
        }
    }
    foreach ($k in @('LsaxPhase0Probe.dll', ($script:SqlDirName + '/LsaxPhase0SqliteProbe.dll'))) {
        if ($manifest.Contains($k)) {
            Write-Lsax ('SHA-256 ' + $k + ' = ' + $manifest[$k].Sha256)
        }
    }
}

if ($bad -gt 0) {
    Exit-Lsax 2 ($bad.ToString() + ' file(s) missing or changed.')
}
Exit-Lsax 0 'All checked files match.'
