# LSAX — Reference Archive Review (READ-ONLY)

Document: LSAX-REFERENCE-REVIEW.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

## 1. Scope and rules

The two supplied archives are **read-only references**. They are **not** implementation baselines.
Nothing in LSAX is derived from their code. They were not patched, rebuilt or redistributed.
Inspection was limited to .NET metadata (assembly/type/member references, user-string heap) and a
partial IL decode of a few methods, done with disposable Python tools
(`phase0-probes/tools/dump_meta.py`, `il_natives.py`, `il_disasm.py`). No decompiled source was
produced or stored.

| Archive | SHA-256 (archive) | Contents |
|---|---|---|
| `1cf350-Sell Vehicles v1.2.zip` | `110362ea5213400d23567ad595256748e4e33e2e8f154da4b61295f03ce61322` | `SellVehicle.dll` (11 776 B), `SellVehicle.pdb` (MSVC PDB 7.00), `README.txt` |
| `db5c90-SellCars.zip` | `d6dca5cef76a0c39ee81a4974abe320881610e37c7c576ce2f74d5a243206a10` | `scripts/SellCars.dll` (13 312 B) |

| File | SHA-256 |
|---|---|
| SellVehicle.dll | `296722f809d6c244d55910991a59df72f56067084226fa03d396ef418db1aa03` |
| SellVehicle.pdb | `ab1da9ec1ccacce8832a64d4ee809b9f93793d75dc772850c576e2d4abd3ab61` |
| SellCars.dll | `166a7f3486864281154f5f44e90983399f38bd949df3590ed95441dc7ac41ac1` |

The PDB contains developer-local absolute source paths. They are personal data, not relevant to
LSAX, and are deliberately not reproduced here.

## 2. Sell Vehicles v1.2 (`SellVehicle.dll`)

**Runtime binding (VERIFIED from metadata):** references `ScriptHookVDotNet3 3.3.2.0`, `mscorlib 4.0`,
`System.Windows.Forms`, `System.Drawing`; target framework attribute `.NETFramework,Version=v4.8`
(from PDB source list). One `Script` subclass `SellVehicle` plus `VehicleInfo` (Name, Price, Model,
GXT, Make) and `VehicleDataLoader`.

**Observed behaviour (VERIFIED from metadata + partial IL):**
- Sell point is a fixed world marker (`World.DrawMarker`, `World.CreateBlip`); key or
  `Control` press triggers sale when the player is inside the marker and in a vehicle.
- Vehicle catalogue is read from `scripts/PremiumDeluxeMotorsport/Vehicles/*.ini` (strings
  `PremiumDeluxeMotorsport`, `Vehicles`, `*.ini`, keys `name/price/model/gxt/make`), keyed by
  `GET_HASH_KEY(model)` into a `Dictionary`. It therefore **depends on another mod's data files**.
- Price = INI price × piecewise-linear function of `Entity.Health` with thresholds
  900 / 700 / 500 (e.g. `0.85 + (health−900)/100 × 0.10` above 900; `0.70 + (health−700)/200 × 0.15`
  above 700 …). Condition label (`Very Good/Good/Bad/Very Bad`) uses the same thresholds.
- Payment writes `Player.Money` directly, then `PoolObject.Delete()` on the vehicle.
- All UI strings are hardcoded English literals with GTA colour codes (`~g~`, `~r~`…).

**Lessons for LSAX (observations, not adopted code):**

| # | Observation | LSAX consequence | Label |
|---|---|---|---|
| R1 | Value derived only from model list price × `Entity.Health` | This is the `basePrice * health` anti-pattern the brief forbids. LSAX valuation uses durable simulated condition + history (LSAX-VALUATION-MODEL.md). | DESIGN DECISION |
| R2 | Model-keyed catalogue: two vehicles of the same model are indistinguishable | Confirms need for per-vehicle identity (LSAX-DOMAIN-MODEL.md §4). | DESIGN DECISION |
| R3 | Money write + entity delete are two unjournaled side effects; a crash between them loses one | LSAX Transaction Core journals intent before any side effect and makes each step idempotent (LSAX-TRANSACTION-STATE-MACHINE.md). | DESIGN DECISION |
| R4 | Hard dependency on another mod's INI folder | LSAX catalogue/MSRP data is LSAX-owned; external catalogues may only be optional importers with validation. | DESIGN DECISION |
| R5 | Hardcoded English strings | LSAX forbids user-facing literals; RU primary + EN parity (LSAX-LOCALIZATION-CONTRACT.md). | DESIGN DECISION |
| R6 | `GET_HASH_KEY` over model names is a workable model-key technique on SHVDN3 | LSAX may key catalogue rows by model hash **and** keep the model name string for add-ons/diagnostics. | DESIGN DECISION |

## 3. SellCars (`SellCars.dll`)

**Runtime binding (VERIFIED from metadata):** references `ScriptHookVDotNet2 2.11.6.0` (the SHVDN v2
API, not v3). One `Script` subclass `SellCars.SellCars` with obfuscated-looking short member names.

**Observed behaviour (VERIFIED from metadata + native-hash IL scan):**
- "Illegal Car Market" (blip name): fixed payout `$3000` (hardcoded in the help strings), uses
  `Ped.LastVehicle` and a distance check (`"Your last car isn't close enough."`).
- Spawns buyer peds from a fixed model list (`a_m_m_prolhost_01`, …), sets
  `IsInvincible`, flee/combat attributes, `SET_BLOCKING_OF_NON_TEMPORARY_EVENTS`.
- Handover scene: `CREATE_SYNCHRONIZED_SCENE` + `TASK_SYNCHRONIZED_SCENE` +
  `PLAY_SYNCHRONIZED_ENTITY_ANIM`, cash envelope prop, ambient speech, `SET_TABLE_GAMES_CAMERA_THIS_UPDATE`.
- Buyer takes the car: `Tasks.EnterVehicle` then `Tasks.DriveTo`; `Game.GameTime` is sampled
  9 times in `onTick`, consistent with timer-gated phases (exact timeout semantics were not decoded).
- `Game.FadeScreenOut/In` + `Entity.Position` set (teleport during scene).
- `Script.Aborted` handler deletes spawned entities (`DOES_ENTITY_EXIST` guard) — cleanup on unload.
- Contains a generic `File.ReadAllLines/WriteAllLines` line-replace helper; no path literal is
  present in the user-string heap, so its use could not be established.

**Lessons for LSAX:**

| # | Observation | LSAX consequence | Label |
|---|---|---|---|
| R7 | Synchronized-scene handover with ped + prop + cash is feasible on SHVDN (it shipped) | A physical handover scene is plausible for Stage 10; LSAX will re-derive it behind a world-adapter with explicit timeouts. | ASSUMPTION (runtime not re-tested here) |
| R8 | Buyer ped drives off with the player's car via ped tasks | Tasks can fail/stall (blocked paths, RDE police, ped death). LSAX bounds every world task by timeout + retry + fallback + abort (LSAX-TRANSACTION-STATE-MACHINE.md §9). | DESIGN DECISION |
| R9 | `Aborted` cleanup of spawned entities | LSAX world adapters own a bounded registry of spawned entities, released on abort/shutdown and on startup (orphan sweep limited to LSAX-tagged entities). | DESIGN DECISION |
| R10 | Fixed payout, no stolen/provenance model, no Heat | LSAX Underground valuation includes provenance, Heat and haircut (LSAX-HEAT-AND-UNDERGROUND-MODEL.md). | DESIGN DECISION |
| R11 | `IsInvincible` buyer peds + blocking events | Must not be used in a way that conflicts with RDE/SixStar or RealParamedics ownership; LSAX scene peds are LSAX-owned and short-lived; no global ped policy (LSAX-COMPATIBILITY-CONTRACT.md). | DESIGN DECISION |
| R12 | Screen fade + teleport | Teleport by any script is a signal the LSAX odometer must reject (LSAX-MASTER-SPEC §07). | DESIGN DECISION |
| R13 | Built against SHVDN v2 API | LSAX targets the SHVDN **v3** API only (scripting_v3). | DESIGN DECISION |

## 4. What the references do not provide

Neither reference persists per-vehicle identity, mileage, history, provenance, transactions, or
localisation. Neither handles save/load. Neither offers evidence on save/load signals, decorator
survival, handle reuse or SQLite loading. Those questions are handled only in
`LSAX-SAVELOAD-FEASIBILITY.md` and `feasibility.md`.
