# LSAX MASTER SPEC v1.0 DRAFT1 — Package Index

**Status:** DRAFT 1 for an independent READ-ONLY specification audit. **Not SPEC_APPROVED** — the author does not grant
approval, and the author's own checklist marks one gate item FAIL: **BLOCKER B-01** (save/load runtime assumptions
unproven; exact experiment ready in `phase0-probes/`). See `spec/LSAX-MASTER-SPEC-v1.0.md` Appendix L.

**No production LSAX code or DLL is included.** `phase0-probes/` contains *disposable* feasibility probes (C#, never
executed; compile-checked only) and *reference simulations* (Python) used to prove contract logic and to generate the
worked numbers. Both are marked "NOT PRODUCTION CODE" in every file.

## Reading order for the auditor

1. `spec/LSAX-MASTER-SPEC-v1.0.md` — sections 00–30, appendix map, SPEC_APPROVED self-assessment
2. `spec/LSAX-SAVELOAD-FEASIBILITY.md` — the P0 risk, model comparison, decision record, exact experiment
3. `feasibility.md` — every evidence item (E0–E8) with its label and source
4. `spec/LSAX-TRANSACTION-STATE-MACHINE.md`, `spec/LSAX-DOMAIN-MODEL.md`, `spec/LSAX-TIME-MODEL.md`, `spec/LSAX-DB-SCHEMA-DRAFT.md`
5. `spec/LSAX-VALUATION-MODEL.md`, `spec/LSAX-NPC-GENERATION-MODEL.md`, `spec/LSAX-HEAT-AND-UNDERGROUND-MODEL.md`
6. `spec/LSAX-LOCALIZATION-CONTRACT.md`, `spec/LSAX-COMPATIBILITY-CONTRACT.md`, `spec/LSAX-PERFORMANCE-BUDGET.md`
7. `spec/LSAX-TEST-STRATEGY.md`, `spec/LSAX-STAGE-ACCEPTANCE.md`, `spec/LSAX-RISK-REGISTER.md`, `spec/LSAX-REFERENCE-REVIEW.md`
8. `decisions.md`, `risks.md`, `progress.md` — durable working state (includes every sim-driven design correction)

## Required deliverables → files

| Required (05-CLAUDE-OPUS-PHASE0-PROMPT) | File |
|---|---|
| LSAX-MASTER-SPEC-v1.0.md | `spec/LSAX-MASTER-SPEC-v1.0.md` |
| LSAX-DOMAIN-MODEL.md … LSAX-REFERENCE-REVIEW.md (15 files) | same names, in `spec/` |
| progress.md, decisions.md, risks.md, feasibility.md | package root |
| SHA-256 manifest | `MANIFEST.sha256` (covers every other file; verify with `sha256sum -c MANIFEST.sha256` inside the package root) |

## Evidence map

| Evidence | Where |
|---|---|
| SHVDN source facts (lifecycle, money, decorators, assembly loading) | `feasibility.md` E1–E6, pinned `scripthookvdotnet/scripthookvdotnet@56ba3bfb267a51431716bfbd92409228c718753d` |
| Native existence / absence checks | `evidence/native_check.txt`, `evidence/save_natives_scan.txt`, `evidence/forbidden_natives_check.txt`; pinned `alloc8or/gta5-nativedb-data@424fb51b089049a9fbcebcc641500b1d44d255b4`, natives.json SHA-256 `d13c7e8d627dfe4eab11ba1c25b3621562ceebfe68b0fb5cfc0644d47469b441` |
| Reference archive inspection (metadata only) | `evidence/ref_*_metadata.txt`, `spec/LSAX-REFERENCE-REVIEW.md` |
| Simulation outputs (+ source hashes) | `evidence/sim/*.out.md`, `evidence/sim/SUMMARY.md` |
| Probe sources, procedure, pass criteria | `phase0-probes/README-PROBES.md`, `phase0-probes/shvdn/` |

## Reproduce

```
python3 phase0-probes/sim/run_all.py          # all reference simulations, ~2–3 min, Python 3.11 stdlib only
python3 phase0-probes/tools/xref_check.py     # cross-reference audit of this package (IDs, paths, sections)
dotnet build phase0-probes/shvdn/LsaxPhase0Probe -c Release          # compile check (.NET SDK 8, NuGet)
dotnet build phase0-probes/shvdn/LsaxPhase0SqliteProbe -c Release
```

## Inputs (read-only)

| Input | SHA-256 |
|---|---|
| LSAX-PHASE0-V3-PACK.zip (contents verified against its SHA256SUMS.txt: 6/6 OK) | `3ed73d4045db246468d5453904eeff5aabbf1dbf682ef752e29643a28e536d48` |
| 1cf350-Sell Vehicles v1.2.zip (reference only) | `110362ea5213400d23567ad595256748e4e33e2e8f154da4b61295f03ce61322` |
| db5c90-SellCars.zip (reference only) | `d6dca5cef76a0c39ee81a4974abe320881610e37c7c576ce2f74d5a243206a10` |

## Environment limits (stated, not hidden)

Phase 0 ran in a Linux container without GTA V. Nothing here is VERIFIED at runtime. Labels used: VERIFIED (source |
compile | sim), DESIGN DECISION, ASSUMPTION, OPEN RISK, BLOCKER.
