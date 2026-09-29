# =====================================================================================
# PREPARE-EVIDENCE-FOLDER - copies evidence-template\ to evidence-work\ (inside the pack folder) so the owner
# fills in copies, never the templates. Never overwrites an existing file. Touches nothing outside the pack.
# NOT LSAX PRODUCTION CODE. Exit codes: 0 ok, 2 template missing.
# =====================================================================================
param()

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

$pack = Get-PackRoot
$created = 0
foreach ($cfg in $script:ConfigNames) {
    $srcDir = Join-Rel $pack ('evidence-template/' + $cfg)
    $dstDir = Join-Rel $pack ('evidence-work/' + $cfg)
    if (-not (Test-Path -LiteralPath $srcDir -PathType Container)) {
        Exit-Lsax 2 ('Template folder missing: evidence-template/' + $cfg)
    }
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    foreach ($f in (Get-ChildItem -LiteralPath $srcDir -File)) {
        $dst = Join-Path $dstDir $f.Name
        if (Test-Path -LiteralPath $dst) {
            Write-Lsax ('  exists, kept: evidence-work\' + $cfg + '\' + $f.Name)
            continue
        }
        Copy-Item -LiteralPath $f.FullName -Destination $dst
        Write-Lsax ('  created: evidence-work\' + $cfg + '\' + $f.Name)
        $created++
    }
}
Exit-Lsax 0 ('evidence-work ready (' + $created + ' new file(s)). Fill in ENVIRONMENT.txt and TEST-LOG.tsv there.')
