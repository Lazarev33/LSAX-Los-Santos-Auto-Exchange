Mode: audit-grade (200 episodes); total run time 199.1 s (simulations + regressions, one CPU, Python 3.11.15).

| Simulation | Result | Run time | Source SHA-256 |
|---|---|---:|---|
| `lsax_ref_math.py` | PASS | 0.0 s | `476c81b6c58d9fd076c2d5278cfbc5043ab67810a80c73aea3f2de4c4129fc65` |
| `valuation_ref.py` | PASS | 0.2 s | `70dae32505ef6cb7178a653987e915f00f40903587d5165178a4b948e3fd4f6a` |
| `npcgen_ref.py` | PASS | 7.0 s | `36091aca04b30f6d217160d78a628c9ca4e76b38eff0f6bf16004d4b83df800a` |
| `heat_ref.py` | PASS | 0.0 s | `d35a7435044ae5190c221cd18084b561a884789cef99ca409627bb54c4993729` |
| `identity_ref.py` | PASS | 12.0 s | `0ad6fc51668f4be40673b817105a027c0d9eb508fa542b3381b0cae994223319` |
| `time_ref.py` | PASS | 0.0 s | `d00baa28cec425875b83baa5d77c81e5e1b11c1e1c7149c7c2e14c5f32488786` |
| `sysjournal_ref.py` | PASS | 0.0 s | `dcebda67b27a8d3119a116166c373c5f9caae37b8d7a0dfc023bc27ede3026a1` |
| `legacy_ref.py` | PASS | 0.0 s | `30835b17c448ea2eccc4e20ddf5c47e60a1cd24d331bfe5efd5bea7cbb137f0c` |
| `journal_timeline_ref.py --episodes 200` | PASS | 158.6 s | `f78dd7aec9b6fb5bd8f3c86a2071c7b5b17b0820863107f09d3711fe5c978346` |

Correction regressions (`phase0-probes/regress/run_regressions.py`, details in `evidence/regress/`): PASS
