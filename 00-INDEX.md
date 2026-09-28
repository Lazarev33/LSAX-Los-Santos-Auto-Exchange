# LSAX MASTER SPEC v1.0 DRAFT2 — Package Index

**Status:** DRAFT 2 = Correction Pass 1 after the independent read-only audit of DRAFT 1 (verdict CORRECTION_REQUIRED —
SPEC_APPROVED BLOCKED; 4 P0, 6 P1, 1 P2). **Not SPEC_APPROVED** — the author does not grant approval. Correction-pass
status: **OFFLINE_CORRECTION_COMPLETE — RUNTIME_VALIDATION_REQUIRED** (BLOCKER B-01 and the RUNTIME-closure P1 rows
stay open until the owner returns the logs of `phase0-probes/README-PROBES.md`; see `LSAX-PHASE0-CORRECTION-1-REPORT.md`).

**No production LSAX code or DLL is included.** `phase0-probes/` contains *disposable* feasibility probes (C#, never
executed in GTA V; compile-checked only), *reference models* (Python, `sim/`), *deterministic correction regressions*
(Python, `regress/`) and one disposable .NET API check (`dotnet-checks/`). All are marked "NOT PRODUCTION CODE".
DRAFT 1 (`LSAX-MASTER-SPEC-v1.0-DRAFT1.zip`, SHA-256 `281f52f6e989ed7de93d4af7d61e25e9a2369fa7d74856f5d666357896cccd16`)
is unchanged and is not part of this package.

## Reading order for the re-auditor

1. `LSAX-PHASE0-CORRECTION-1-REPORT.md` — every audit finding: verification, correction, files, regression, result
2. `spec/LSAX-MASTER-SPEC-v1.0.md` — sections 00–30, glossary, appendix map, SPEC_APPROVED self-assessment (App. L)
3. `spec/LSAX-SAVELOAD-FEASIBILITY.md` — positive-evidence anchoring, exact runtime experiment (§6), fallbacks (§7)
4. `spec/LSAX-TRANSACTION-STATE-MACHINE.md` — own-evidence recovery (§7), system transactions (§3a), matrix (§10)
5. `phase0-probes/README-PROBES.md` — the runtime validation package (install, launch, T1–T17, PASS/FAIL, cleanup)
6. `feasibility.md` — every evidence item (E0–E9) with label and source; E8-5 (DRAFT1 journal sim) is superseded
7. `spec/LSAX-DOMAIN-MODEL.md`, `spec/LSAX-TIME-MODEL.md`, `spec/LSAX-DB-SCHEMA-DRAFT.md`, `spec/LSAX-NPC-GENERATION-MODEL.md`
8. remaining `spec/` documents; `decisions.md`, `risks.md`, `progress.md` (durable working state, finding ledger)

## Required deliverables → files

| Required | File |
|---|---|
| complete corrected Phase-0 specification | `spec/` (16 documents, all DRAFT2) + `progress.md`, `decisions.md`, `risks.md`, `feasibility.md` |
| correction report | `LSAX-PHASE0-CORRECTION-1-REPORT.md` |
| deterministic regressions (audit reproduction imported) | `phase0-probes/regress/` (`audit/repro_findings.py` byte-identical to the audit bundle) |
| reference simulations | `phase0-probes/sim/` |
| runtime validation package | `phase0-probes/README-PROBES.md`, `phase0-probes/shvdn/`, `phase0-probes/probe.ini.sample` |
| SHA-256 manifest | `MANIFEST.sha256` (covers every other file; `sha256sum -c MANIFEST.sha256` inside the package root) |

## Evidence map

| Evidence | Where |
|---|---|
| SHVDN source facts (lifecycle, money, decorators, assembly loading) | `feasibility.md` E1–E6, pinned `scripthookvdotnet/scripthookvdotnet@56ba3bfb267a51431716bfbd92409228c718753d` |
| Native existence / absence checks | `evidence/native_check.txt`, `evidence/save_natives_scan.txt`, `evidence/forbidden_natives_check.txt`; pinned `alloc8or/gta5-nativedb-data@424fb51b089049a9fbcebcc641500b1d44d255b4`, natives.json SHA-256 `d13c7e8d627dfe4eab11ba1c25b3621562ceebfe68b0fb5cfc0644d47469b441` |
| Reference archive inspection (metadata only) | `evidence/ref_*_metadata.txt`, `spec/LSAX-REFERENCE-REVIEW.md` |
| Reference simulation outputs (+ source hashes, run times) | `evidence/sim/*.out.md`, `evidence/sim/SUMMARY.md` |
| Correction regression outputs (+ source hashes) | `evidence/regress/*.out.md`, `evidence/regress/SUMMARY.md` |
| Probe compile logs; .NET backup API check | `evidence/compile/` |
| Probe sources, procedure, pass criteria | `phase0-probes/README-PROBES.md`, `phase0-probes/shvdn/` |

## Reproduce

```
python3 phase0-probes/sim/run_all.py            # fast: every reference model + all regressions (~1.5 min)
python3 phase0-probes/sim/run_all.py --audit    # audit grade: journal model 200 episodes per mix x granularity (~3.5 min)
python3 phase0-probes/regress/run_regressions.py   # correction regressions only (~15 s)
python3 phase0-probes/tools/xref_check.py       # cross-reference + stale-term audit of this package
dotnet build phase0-probes/shvdn/LsaxPhase0Probe -c Release          # compile check (.NET SDK 8, NuGet)
dotnet build phase0-probes/shvdn/LsaxPhase0SqliteProbe -c Release
dotnet run -c Release --project phase0-probes/dotnet-checks/backupcheck   # D-DB-4 backup API on .NET 8
```

## Inputs (read-only)

| Input | SHA-256 |
|---|---|
| LSAX-PHASE0-V3-PACK.zip (contents verified against its SHA256SUMS.txt: 6/6 OK) | `3ed73d4045db246468d5453904eeff5aabbf1dbf682ef752e29643a28e536d48` |
| 1cf350-Sell Vehicles v1.2.zip (reference only) | `110362ea5213400d23567ad595256748e4e33e2e8f154da4b61295f03ce61322` |
| db5c90-SellCars.zip (reference only) | `d6dca5cef76a0c39ee81a4974abe320881610e37c7c576ce2f74d5a243206a10` |
| LSAX-PHASE0-INDEPENDENT-AUDIT.zip (SHA256SUMS.txt 4/4 OK) | `35d3c55d503ad398e574d267fdd59ea0d15882dcd2573548c7a3399b08995bb2` |
| Audited baseline (DRAFT1 head) | commit `f6aff47d1dbea94576d6aae1f60bd17102d549cc` |

## Environment limits (stated, not hidden)

Phase 0 and Correction Pass 1 ran in a Linux container without GTA V. Nothing here is VERIFIED at runtime. Labels
used: VERIFIED (source | compile | sim), DESIGN DECISION, ASSUMPTION, OPEN RISK, BLOCKER.
