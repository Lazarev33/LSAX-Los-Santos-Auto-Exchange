# =====================================================================================
# CHECK-LOG - READ-ONLY reader of the probe logs of the CURRENT run (<scripts>\LSAXProbe\).
# NOT LSAX PRODUCTION CODE.
#   -Step S4 .. S10 : smoke-test gates of 01-SMOKE-TEST-RU.md. A smoke gate is NOT an acceptance decision:
#                     PC-1..PC-8 / P-DB-01 / P-ID-01 are decided only by the independent reviewer from the
#                     returned logs (03-PASS-FAIL-RULES.md). "SMOKE ... OK" means only "continue".
#   -Step SUMMARY   : prints what the logs contain (counts, CTOR rows, save-file rows, errors). No verdict.
# Writes only into the pack folder: evidence-work\<Config>\smoke-state.txt and check-log-output.txt.
# Exit codes: 0 ok, 10 smoke gate failed (STOP), 1 invalid input/order, 6 not installed / no logs.
# =====================================================================================
param(
    [string]$GtaRoot,
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][ValidateSet('S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10', 'SUMMARY')][string]$Step
)

. (Join-Path $PSScriptRoot 'LsaxPack.Common.ps1')

$pack = Get-PackRoot
$work = Get-EvidenceWorkDir $pack $Config
New-Item -ItemType Directory -Force -Path $work | Out-Null
$outFile = Join-Path $work 'check-log-output.txt'
$stateFile = Join-Path $work 'smoke-state.txt'
$gta = Resolve-GtaRoot $GtaRoot
$scripts = Resolve-ScriptsDir $gta $false
$probeDir = Join-Path $scripts $script:ProbeDirName
if (-not (Test-Path -LiteralPath (Get-InstallManifestPath $scripts) -PathType Leaf)) {
    Exit-Lsax 6 'The probes are not installed by this pack here (no manifest).'
}

$script:Out = New-Object System.Collections.ArrayList
function Say([string]$s) {
    Write-Host $s
    [void]$script:Out.Add($s)
}

function Read-Events([string[]]$Files) {
    $list = New-Object System.Collections.ArrayList
    foreach ($f in $Files) {
        foreach ($line in (Read-SharedLines $f)) {
            $p = $line.Split("`t")
            if ($p.Length -lt 2) {
                continue
            }
            $data = ''
            if ($p.Length -ge 3) {
                $data = ($p[2..($p.Length - 1)] -join "`t")
            }
            [void]$list.Add((New-Object PSObject -Property @{ I = $list.Count; Utc = $p[0]; Evt = $p[1]; Data = $data }))
        }
    }
    return , $list
}

function Fld([string]$Data, [string]$Pattern) {
    $m = [regex]::Match($Data, $Pattern)
    if ($m.Success) {
        return $m.Groups[1].Value
    }
    return $null
}

function Evts($List, [string]$Name, [int]$AfterIndex) {
    return @($List | Where-Object { $_.Evt -eq $Name -and $_.I -gt $AfterIndex })
}

$probeLogs = @(Get-ChildItem -LiteralPath $probeDir -File -Filter 'probe-*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'probe-*.log' } | Sort-Object Name | ForEach-Object { $_.FullName })
$sqlLogPath = Join-Path $probeDir 'sqlite-probe.log'
$ev = Read-Events $probeLogs
$sq = New-Object System.Collections.ArrayList
if (Test-Path -LiteralPath $sqlLogPath -PathType Leaf) {
    $sq = Read-Events @($sqlLogPath)
}

$state = [ordered]@{}
if (Test-Path -LiteralPath $stateFile -PathType Leaf) {
    foreach ($line in [System.IO.File]::ReadAllLines($stateFile)) {
        $eq = $line.IndexOf('=')
        if ($eq -gt 0) {
            $state[$line.Substring(0, $eq)] = $line.Substring($eq + 1)
        }
    }
}
function Save-State {
    $sb = New-Object System.Text.StringBuilder
    foreach ($k in $state.Keys) {
        [void]$sb.Append($k + '=' + $state[$k] + "`r`n")
    }
    Write-TextFile $stateFile $sb.ToString()
}

$ctors = @($ev | Where-Object { $_.Evt -eq 'CTOR' })
$lastCtor = $null
$prevCtor = $null
$lastCtorI = -1
if ($ctors.Count -gt 0) {
    $lastCtor = $ctors[$ctors.Count - 1]
    $lastCtorI = $lastCtor.I
}
if ($ctors.Count -gt 1) {
    $prevCtor = $ctors[$ctors.Count - 2]
}
$nSaveChanged = @($ev | Where-Object { $_.Evt -eq 'SAVEFILE_CHANGED' }).Count
$nSqlCtor = @($sq | Where-Object { $_.Evt -eq 'SQL_CTOR' }).Count
$nErr = @($ev | Where-Object { $_.Evt -eq 'PROBE_ERROR' }).Count
$nInterleave = @($ev | Where-Object { $_.Evt -eq 'TICK_INTERLEAVE' }).Count
$nPtDec = @($ev | Where-Object { $_.Evt -eq 'PT_DECREASED' }).Count
$nSqlFail = @($sq | Where-Object { $_.Evt -eq 'SQL_FAIL' }).Count

Say ('==== ' + $script:LsaxPackName + ' CHECK-LOG ' + $Step + ' config=' + $Config + ' local=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' ====')
Say ('probe log files: ' + $probeLogs.Count + ', rows: ' + $ev.Count + ', sqlite-probe.log rows: ' + $sq.Count)

# ---------------------------------------------------------------- SUMMARY (no verdict)
if ($Step -eq 'SUMMARY') {
    $groups = $ev | Group-Object Evt | Sort-Object Name
    foreach ($g in $groups) {
        Say ('  ' + $g.Name + ' = ' + $g.Count)
    }
    Say 'CTOR rows (n, utc, domainInstanceInProcess, process, TOKEN_AT_CTOR present):'
    $n = 0
    foreach ($c in $ctors) {
        $n++
        $tok = @(Evts $ev 'TOKEN_AT_CTOR' $c.I) | Select-Object -First 1
        $pres = '-'
        if ($tok) {
            $pres = Fld $tok.Data 'present=(\d)'
        }
        Say ('  #' + $n + ' ' + $c.Utc + ' dom=' + (Fld $c.Data 'domainInstanceInProcess=(\d+)') + ' proc=' + (Fld $c.Data 'process=(\S+)') + ' present=' + $pres)
    }
    Say 'SAVEFILE_CHANGED rows (utc, file, signalSeen):'
    foreach ($s in @($ev | Where-Object { $_.Evt -eq 'SAVEFILE_CHANGED' })) {
        Say ('  ' + $s.Utc + ' ' + (Fld $s.Data 'file=(\S+)') + ' signalSeen=' + (Fld $s.Data 'signalSeen=(\d)'))
    }
    foreach ($s in @($ev | Where-Object { $_.Evt -eq 'PROBE_ERROR' })) {
        Say ('  PROBE_ERROR ' + $s.Utc + ' ' + $s.Data)
    }
    $sg = $sq | Group-Object Evt | Sort-Object Name
    foreach ($g in $sg) {
        Say ('  sqlite ' + $g.Name + ' = ' + $g.Count)
    }
    Say 'SUMMARY only - no PASS/FAIL. The independent reviewer decides from the returned logs.'
    Add-Content -LiteralPath $outFile -Value $script:Out -Encoding UTF8
    Exit-Lsax 0 'Summary printed.'
}

# ---------------------------------------------------------------- smoke gates
$checks = New-Object System.Collections.ArrayList
function Gate([string]$Name, [bool]$Ok, [string]$Detail) {
    $tag = 'FAILED'
    if ($Ok) {
        $tag = 'ok    '
    }
    Say ('  [' + $tag + '] ' + $Name + ' :: ' + $Detail)
    [void]$checks.Add($Ok)
}
function Info([string]$s) {
    Say ('  [info  ] ' + $s)
}
function Need-State([string]$Key) {
    if (-not $state.Contains($Key) -or $state[$Key] -ne '1') {
        Say ('Smoke steps must be checked in order; ' + $Key + ' is not recorded as OK.')
        Add-Content -LiteralPath $outFile -Value $script:Out -Encoding UTF8
        Exit-Lsax 1 ('Run the previous CHECK-LOG step first (' + $Key + ').')
    }
}
function Common-Errors {
    Gate 'no PROBE_ERROR rows in this run' ($nErr -eq 0) ('count=' + $nErr)
    Gate 'no TICK_INTERLEAVE rows in this run' ($nInterleave -eq 0) ('count=' + $nInterleave)
    Gate 'no PT_DECREASED rows in this run' ($nPtDec -eq 0) ('count=' + $nPtDec)
}
function Token-After([int]$Index) {
    return (@(Evts $ev 'TOKEN_AT_CTOR' $Index) | Select-Object -First 1)
}
function TokenSet-After([int]$Index) {
    return (@(Evts $ev 'TOKEN_SET' $Index) | Select-Object -First 1)
}
function Gate-TokenSet([int]$Index) {
    $ts = TokenSet-After $Index
    $ok = $false
    $d = 'missing'
    if ($ts) {
        $d = $ts.Data
        $ok = ((Fld $ts.Data 'setOk=(\d)') -eq '1') -and ((Fld $ts.Data 'readBack=(\d)') -eq '1')
    }
    Gate 'TOKEN_SET setOk=1 readBack=1 after the last CTOR' $ok $d
}
function Gate-SameProcessNext {
    $ok = $false
    $d = 'fewer than two CTOR rows'
    if ($lastCtor -and $prevCtor) {
        $p1 = Fld $prevCtor.Data 'process=(\S+)'
        $p2 = Fld $lastCtor.Data 'process=(\S+)'
        $d1 = [int](Fld $prevCtor.Data 'domainInstanceInProcess=(\d+)')
        $d2 = [int](Fld $lastCtor.Data 'domainInstanceInProcess=(\d+)')
        $ok = ($p1 -eq $p2) -and ($d2 -eq $d1 + 1)
        $d = 'previous dom=' + $d1 + ' proc=' + $p1 + ' / last dom=' + $d2 + ' proc=' + $p2
    }
    Gate 'last CTOR is the next domain of the SAME game process' $ok $d
}

$gateStep = $Step
if ($Step -eq 'S4') {
    # S4 is the first gate: a new smoke attempt on this configuration starts with an empty state.
    $state.Clear()
}
Say ('Smoke gate ' + $Step + ' (01-SMOKE-TEST-RU.md). A gate is not an acceptance decision.')
switch ($Step) {
    'S4' {
        Gate 'at least one CTOR row' ($ctors.Count -ge 1) ('CTOR rows=' + $ctors.Count)
        if ($lastCtor) {
            $dom = Fld $lastCtor.Data 'domainInstanceInProcess=(\d+)'
            Gate 'last CTOR domainInstanceInProcess=1 (T1 expectation)' ($dom -eq '1') ('domainInstanceInProcess=' + $dom)
            Info ('SHVDN assembly version: ' + (Fld $lastCtor.Data 'shvdnAsm=(\S+)') + ', SHVDN file version: ' + (Fld $lastCtor.Data 'shvdnFileVersion=(\S+)') + ', gameVersion enum: ' + (Fld $lastCtor.Data 'gameVersion=(\S+)'))
            $tok = Token-After $lastCtorI
            $ok = $false
            $d = 'missing'
            if ($tok) {
                $d = $tok.Data -replace 'persisted=\[[^\]]*\]', 'persisted=[..]'
                $ok = ((Fld $tok.Data 'registered=(\d)') -eq '1') -and ((Fld $tok.Data 'present=(\d)') -eq '0')
            }
            Gate 'TOKEN_AT_CTOR registered=1 present=0' $ok $d
            Gate-TokenSet $lastCtorI
            $fp = @(Evts $ev 'CTOR_FP' $lastCtorI) | Select-Object -First 1
            $pt = ''
            if ($fp) {
                $pt = Fld $fp.Data ' pt=(\S*)'
            }
            Gate 'CTOR_FP lists at least one play-time candidate stat (pt=...)' (-not [string]::IsNullOrEmpty($pt)) ('pt=' + $pt)
            $nInit = @(Evts $ev 'SAVEFILE_INITIAL' $lastCtorI).Count
            $nMiss = @($ev | Where-Object { $_.Evt -eq 'SAVEROOT_MISSING' }).Count
            Gate 'SAVEFILE_INITIAL rows present, no SAVEROOT_MISSING' (($nInit -ge 1) -and ($nMiss -eq 0)) ('SAVEFILE_INITIAL=' + $nInit + ' SAVEROOT_MISSING=' + $nMiss)
            $nLm = @(Evts $ev 'LOAD_MATCH' $lastCtorI).Count
            Gate 'LOAD_MATCH rows present' ($nLm -ge 1) ('LOAD_MATCH=' + $nLm)
        }
        Gate 'no PROBE_ERROR rows in this run' ($nErr -eq 0) ('count=' + $nErr)
    }
    'S5' {
        Need-State 'S4_OK'
        $since = [int]$state['S4_SAVECHANGED']
        $rows = @($ev | Where-Object { $_.Evt -eq 'SAVEFILE_CHANGED' } | Select-Object -Skip $since)
        Gate 'exactly one new SAVEFILE_CHANGED row since S4 (one save)' ($rows.Count -eq 1) ('new rows=' + $rows.Count)
        $sig = @($rows | Where-Object { (Fld $_.Data 'signalSeen=(\d)') -eq '1' })
        Gate 'that row has signalSeen=1' (($rows.Count -eq 1) -and ($sig.Count -eq 1)) (($rows | ForEach-Object { (Fld $_.Data 'file=(\S+)') + ' signalSeen=' + (Fld $_.Data 'signalSeen=(\d)') }) -join '; ')
        Gate 'no new CTOR since S4 (a save does not reload)' ($ctors.Count -eq [int]$state['S4_CTORS']) ('CTOR rows now=' + $ctors.Count + ' at S4=' + $state['S4_CTORS'])
        Common-Errors
        if ($sig.Count -ge 1) {
            $state['S5_FILE'] = Fld $sig[0].Data 'file=(\S+)'
        }
    }
    'S6' {
        Need-State 'S5_OK'
        Gate 'exactly one new CTOR since S5 (the load)' ($ctors.Count -eq [int]$state['S5_CTORS'] + 1) ('CTOR rows now=' + $ctors.Count + ' at S5=' + $state['S5_CTORS'])
        Gate-SameProcessNext
        $tok = Token-After $lastCtorI
        $ok = $false
        $d = 'missing'
        if ($tok) {
            $d = 'present=' + (Fld $tok.Data 'present=(\d)')
            $ok = (Fld $tok.Data 'present=(\d)') -eq '0'
        }
        Gate 'TOKEN_AT_CTOR present=0 after the load' $ok $d
        Gate-TokenSet $lastCtorI
        $file = $state['S5_FILE']
        $lm = @(Evts $ev 'LOAD_MATCH' $lastCtorI)
        $hit = @($lm | Where-Object { ((Fld $_.Data 'matches=(\d+)') -eq '1') -and ($_.Data -match ('\[' + [regex]::Escape($file) + ':W(=|\?)\]')) })
        Gate ('LOAD_MATCH matches=1 [' + $file + ':W= or :W?] for at least one candidate') ($hit.Count -ge 1) (($lm | ForEach-Object { $_.Data -replace ' cash=\[[^\]]*\]', '' }) -join ' | ')
        Gate 'no SAVEFILE_CHANGED since S5 (a load writes no save)' ($nSaveChanged -eq [int]$state['S5_SAVECHANGED']) ('rows now=' + $nSaveChanged + ' at S5=' + $state['S5_SAVECHANGED'])
        if ($prevCtor) {
            $prevI = $prevCtor.I
            $ab = @($ev | Where-Object { $_.Evt -eq 'ABORTED' -and $_.I -lt $lastCtorI -and $_.I -gt $prevI })
            Info ('ABORTED rows before this CTOR (PC-6, informative): ' + $ab.Count)
        }
        Common-Errors
    }
    'S7' {
        Need-State 'S6_OK'
        Gate 'exactly one new CTOR since S6 (Reload())' ($ctors.Count -eq [int]$state['S6_CTORS'] + 1) ('CTOR rows now=' + $ctors.Count + ' at S6=' + $state['S6_CTORS'])
        Gate-SameProcessNext
        $prevSet = @($ev | Where-Object { $_.Evt -eq 'TOKEN_SET' -and $_.I -lt $lastCtorI }) | Select-Object -Last 1
        $expected = $null
        if ($prevSet) {
            $expected = Fld $prevSet.Data 'token=(\d+)'
        }
        $tok = Token-After $lastCtorI
        $ok = $false
        $d = 'missing'
        if ($tok) {
            $d = 'present=' + (Fld $tok.Data 'present=(\d)') + ' value=' + (Fld $tok.Data 'value=(-?\d+)') + ' expected=' + $expected
            $ok = ((Fld $tok.Data 'present=(\d)') -eq '1') -and ((Fld $tok.Data 'value=(-?\d+)') -eq $expected)
        }
        Gate 'TOKEN_AT_CTOR present=1 with the persisted token (T11 expectation)' $ok $d
        Gate-TokenSet $lastCtorI
        Common-Errors
    }
    'S8' {
        Need-State 'S7_OK'
        Gate 'no new CTOR since S7 (a character switch does not reload)' ($ctors.Count -eq [int]$state['S7_CTORS']) ('CTOR rows now=' + $ctors.Count + ' at S7=' + $state['S7_CTORS'])
        $pc = @(Evts $ev 'TOKEN_PED_CHANGED' $lastCtorI)
        $good = @($pc | Where-Object { ((Fld $_.Data 'newPedHadToken=(\d)') -eq '0') -and ((Fld $_.Data 'retagOk=(\d)') -eq '1') })
        Gate 'TOKEN_PED_CHANGED rows present, every one newPedHadToken=0 retagOk=1' (($pc.Count -ge 1) -and ($good.Count -eq $pc.Count)) ('rows=' + $pc.Count + ' matching=' + $good.Count)
        Common-Errors
    }
    'S9' {
        Need-State 'S8_OK'
        $native = Join-Rel $scripts ($script:SqlDirName + '/e_sqlite3.dll')
        $sqlCtors = @($sq | Where-Object { $_.Evt -eq 'SQL_CTOR' })
        $since = [int]$state['S8_SQLCTORS']
        $new = @($sqlCtors | Select-Object -Skip $since)
        Gate 'at least two new SQL_CTOR blocks since S8 (game start + one Reload())' ($new.Count -ge 2) ('new SQL_CTOR=' + $new.Count)
        $bi = 0
        foreach ($c in $new) {
            $bi++
            $next = @($sqlCtors | Where-Object { $_.I -gt $c.I }) | Select-Object -First 1
            $end = [int]::MaxValue
            if ($next) {
                $end = $next.I
            }
            $blk = @($sq | Where-Object { $_.I -gt $c.I -and $_.I -lt $end })
            $get = { param($n) @($blk | Where-Object { $_.Evt -eq $n }) | Select-Object -First 1 }
            $pre = & $get 'SQL_PRELOAD'
            $open = & $get 'SQL_OPEN'
            $prag = & $get 'SQL_PRAGMAS'
            $snap = & $get 'SQL_SNAPSHOT'
            $jb = & $get 'SQL_JOURNAL_BACKUP'
            $res = & $get 'SQL_RESTORE'
            $tag = 'block ' + $bi + ': '
            Gate ($tag + 'SQL_PRELOAD ok=True for <scripts>\LSAXProbeSql\e_sqlite3.dll') ([bool]$pre -and ($pre.Data -match 'ok=True') -and ((Fld $pre.Data 'path=(.+?) ok=') -ieq $native)) ($(if ($pre) { $pre.Data -replace [regex]::Escape($scripts), '<scripts>' } else { 'missing' }))
            Gate ($tag + 'SQL_OPEN with nativeModule = that file') ([bool]$open -and ((Fld $open.Data 'nativeModule=(.+)$') -ieq $native)) ($(if ($open) { $open.Data -replace [regex]::Escape($scripts), '<scripts>' } else { 'missing' }))
            Gate ($tag + 'SQL_COMMIT_US, SQL_DEPENDENCY, SQL_WATERMARK_AT_START, SQL_TWO_FILE_COMMIT_US present') ([bool](& $get 'SQL_COMMIT_US') -and [bool](& $get 'SQL_DEPENDENCY') -and [bool](& $get 'SQL_WATERMARK_AT_START') -and [bool](& $get 'SQL_TWO_FILE_COMMIT_US')) 'see sqlite-probe.log'
            Gate ($tag + 'SQL_PRAGMAS main.synchronous=2 proj.synchronous=1 proj.journal=wal') ([bool]$prag -and ($prag.Data.Trim() -eq 'main.synchronous=2 proj.synchronous=1 proj.journal=wal')) ($(if ($prag) { $prag.Data } else { 'missing' }))
            Gate ($tag + 'SQL_SNAPSHOT tables=[projection_meta,vehicle]') ([bool]$snap -and $snap.Data.StartsWith('tables=[projection_meta,vehicle] ')) ($(if ($snap) { $snap.Data } else { 'missing' }))
            Gate ($tag + 'SQL_JOURNAL_BACKUP tables=[probe_row]') ([bool]$jb -and ($jb.Data.Trim() -eq 'tables=[probe_row]')) ($(if ($jb) { $jb.Data } else { 'missing' }))
            $okw = [bool]$res -and [bool]$snap -and ((Fld $res.Data 'watermark=(\S+)') -eq (Fld $snap.Data 'watermark=(\S+)'))
            Gate ($tag + 'SQL_RESTORE watermark equals the SQL_SNAPSHOT watermark') $okw ($(if ($res) { $res.Data } else { 'missing' }))
            $two = & $get 'SQL_TWO_FILE_COMMIT_US'
            if ($two) {
                Info ($tag + 'R-DB-2 timing (reviewer decides): ' + $two.Data)
            }
            $ctorData = $c.Data -replace [regex]::Escape($scripts), '<scripts>'
            Info ($tag + 'SQL_CTOR ' + $ctorData)
            foreach ($dep in @($blk | Where-Object { $_.Evt -eq 'SQL_DEPENDENCY' })) {
                $loc = Fld $dep.Data 'location=(.+)$'
                $inside = 'NO'
                try {
                    if ($loc -and (Test-Inside (Join-Path $scripts $script:SqlDirName) $loc)) {
                        $inside = 'yes'
                    }
                }
                catch {
                    $inside = 'NO (location not a path)'
                }
                Info ($tag + 'R-COMP-2 (reviewer decides; see 03 rules U-03): inside LSAXProbeSql=' + $inside + ' :: ' + ($dep.Data -replace [regex]::Escape($scripts), '<scripts>'))
            }
        }
        Gate 'no SQL_FAIL rows in sqlite-probe.log' ($nSqlFail -eq 0) ('count=' + $nSqlFail)
        Gate 'no PROBE_ERROR rows in this run' ($nErr -eq 0) ('count=' + $nErr)
    }
    'S10' {
        foreach ($k in @('S4_OK', 'S5_OK', 'S6_OK', 'S7_OK', 'S8_OK', 'S9_OK')) {
            Need-State $k
        }
        Assert-GameNotRunning
        Common-Errors
        Gate 'no SQL_FAIL rows in sqlite-probe.log' ($nSqlFail -eq 0) ('count=' + $nSqlFail)
        $iniPath = Join-Rel $scripts ($script:ProbeDirName + '/probe.ini')
        $want = Get-TextSha256 (Get-ProfileText $pack 'PSL01' $scripts)
        $have = '<missing>'
        if (Test-Path -LiteralPath $iniPath -PathType Leaf) {
            $have = Get-Sha256 $iniPath
        }
        Gate 'probe.ini is back on profile PSL01 (B-01 settings)' ($have -eq $want) 'run SET-PROBE-CONFIG.cmd -ProbeProfile PSL01 if not'
    }
}

$allOk = -not ($checks -contains $false)
if ($allOk) {
    $state[$gateStep + '_OK'] = '1'
}
else {
    $state[$gateStep + '_OK'] = '0'
}
$state[$gateStep + '_CTORS'] = [string]$ctors.Count
$state[$gateStep + '_SAVECHANGED'] = [string]$nSaveChanged
$state[$gateStep + '_SQLCTORS'] = [string]$nSqlCtor
$state[$gateStep + '_LOCAL'] = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
Save-State
if ($allOk) {
    Say ('SMOKE ' + $gateStep + ': OK - continue with the next smoke step.')
    Add-Content -LiteralPath $outFile -Value $script:Out -Encoding UTF8
    if ($gateStep -eq 'S10') {
        Exit-Lsax 0 'Smoke test complete (gates only - NOT runtime acceptance). Next: COLLECT-EVIDENCE.cmd -Phase SMOKE, then 02-FULL-VALIDATION-T1-T17-RU.md.'
    }
    Exit-Lsax 0 ('Smoke gate ' + $gateStep + ' OK.')
}
Say ('SMOKE ' + $gateStep + ': FAILED - STOP. Do NOT continue to T1-T17. Close GTA, run COLLECT-EVIDENCE.cmd -Phase SMOKE and send the evidence ZIP to the independent reviewer.')
Add-Content -LiteralPath $outFile -Value $script:Out -Encoding UTF8
Exit-Lsax 10 ('Smoke gate ' + $gateStep + ' FAILED - STOP full validation.')
