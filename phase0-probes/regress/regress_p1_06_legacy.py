"""P1-06 regression — first-run LEGACY import cannot launder provenance (decision D-PROV-1; model
phase0-probes/sim/legacy_ref.py).

First-run attempts: stolen car, ambient traffic car, mission/script-owned vehicle, trainer-spawned vehicle, add-on
vehicle, legitimately owned pre-LSAX vehicle — each with and without player opt-in, parked in the player's garage or
not. Normative rule set (LEGACY_TRUSTED empty): nothing becomes CLEAN / legal-eligible. A hypothetical probe-proven
marker rule is exercised to show that only the proven marker (not model, plate, garage or opt-in) could ever qualify.
The title state machine is checked exhaustively: no path from UNKNOWN / STOLEN / UNDERGROUND to CLEAN.
"""
import itertools
import sys

from regress_common import Suite
from legacy_ref import (LEGACY_TRUSTED_RULES, LEGAL_ELIGIBLE, ORIGIN, POSITIVE_ORIGINS, TRANSITIONS, WorldVehicle,
                        classify_import, reachable_from)

SOURCES = {
    "stolen car (taken before LSAX)": dict(model=11, plate="FAKE01"),
    "ambient traffic car": dict(model=12, plate="47KLM123"),
    "mission/script-owned vehicle": dict(model=13, plate="MISSION1", mission_entity=True),
    "trainer-spawned vehicle": dict(model=14, plate="TRAINER1"),
    "add-on vehicle": dict(model=99_001, plate="ADDON001", addon_model=True),
    "legitimately owned pre-LSAX vehicle": dict(model=15, plate="MYCAR001"),
    "trainer copy of the story personal vehicle": dict(model=16, plate="FC1988"),
    "story personal vehicle": dict(model=16, plate="FC1988"),
}


def run():
    s = Suite("P1-06 LEGACY provenance")
    s.check("normative LEGACY_TRUSTED rule set is empty", LEGACY_TRUSTED_RULES == ())

    for name, attrs in SOURCES.items():
        for opt_in, garage in itertools.product((False, True), (False, True)):
            v = WorldVehicle(source=name, player_opt_in=opt_in, in_player_garage=garage, **attrs)
            action, title, cause = classify_import(v)
            tag = f"{name} opt_in={opt_in} garage={garage}"
            if attrs.get("mission_entity"):
                s.check(f"{tag}: excluded (never imported)", action == "EXCLUDED")
            else:
                s.check(f"{tag}: imported as UNKNOWN", (action, title) == ("REGISTER", "UNKNOWN"), (action, title, cause))
            s.check(f"{tag}: not legal-market eligible", title not in LEGAL_ELIGIBLE)

    # A hypothetical future rule that requires a runtime-PROVEN marker (not modelled on model/plate/garage/opt-in).
    rules = (("PROVEN_STORY_MARKER", lambda v: v.proven_marker),)
    real = WorldVehicle(source="story personal vehicle", model=16, plate="FC1988", proven_marker=True)
    copy = WorldVehicle(source="trainer copy", model=16, plate="FC1988", in_player_garage=True, player_opt_in=True)
    s.check("hypothetical proven-marker rule: the marked vehicle would be CLEAN", classify_import(real, rules)[1] == "CLEAN")
    s.check("hypothetical proven-marker rule: a same-model same-plate copy in the garage with opt-in stays UNKNOWN",
            classify_import(copy, rules)[1] == "UNKNOWN")
    unsafe_rule = (("MODEL_PLATE_GARAGE", lambda v: v.model == 16 and v.plate == "FC1988" and v.in_player_garage),)
    s.check("a spoofable rule (model + plate + garage) WOULD launder the trainer copy — why rules need proven markers",
            classify_import(copy, unsafe_rule)[1] == "CLEAN")

    # Title state machine: exhaustive reachability
    for start in ("UNKNOWN", "STOLEN", "UNDERGROUND"):
        s.check(f"no title path {start} -> CLEAN", "CLEAN" not in reachable_from([start]), sorted(reachable_from([start])))
    s.check("every transition into CLEAN is an initial registration with positive provenance",
            all(f is ORIGIN and c in POSITIVE_ORIGINS for f, to, c in TRANSITIONS if to == "CLEAN"))
    s.check("UNKNOWN is never legal-market eligible", "UNKNOWN" not in LEGAL_ELIGIBLE)
    s.check("no verification transition exists (TITLE_VERIFY withdrawn)",
            not any("VERIF" in c for _, _, c in TRANSITIONS))
    s.check("UNKNOWN -> STOLEN on a STOLEN-record identity match", ("UNKNOWN", "STOLEN", "STOLEN_RECORD_MATCH") in TRANSITIONS)
    return s


def main():
    return run().report(verbose=False)


if __name__ == "__main__":
    sys.exit(main())
