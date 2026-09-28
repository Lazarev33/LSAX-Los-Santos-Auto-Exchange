"""LSAX Phase 0 — provenance / title reference model, DRAFT2 (NOT PRODUCTION CODE).

Normative mirror of LSAX-DOMAIN-MODEL.md §5.2 as corrected for audit finding P1-06 and the self-found verification
path (decision D-PROV-1):
  * the LEGACY title is withdrawn; a first-run import yields UNKNOWN unless the vehicle satisfies a rule of the
    LEGACY_TRUSTED set, which is EMPTY until a runtime probe proves an unspoofable ownership marker (P-ID-01, OD-4);
  * a player opt-in / attestation never changes the classification;
  * TITLE_VERIFY is withdrawn: no transition UNKNOWN -> CLEAN exists (a check that can only find STOLEN records
    cannot prove clean provenance); UNKNOWN -> STOLEN happens automatically on an identity match with a STOLEN record;
  * the only ways into CLEAN are origins with positive provenance: NPC generation, LSAX legal delivery, and a
    LEGACY_TRUSTED import (none today). Legal-market eligibility = {CLEAN, SALVAGE, RECOVERED}.
"""
import sys
from collections import deque
from dataclasses import dataclass

TITLES = ("CLEAN", "SALVAGE", "STOLEN", "RECOVERED", "UNDERGROUND", "UNKNOWN")
LEGAL_ELIGIBLE = frozenset({"CLEAN", "SALVAGE", "RECOVERED"})
ORIGIN = None

# (from, to, cause). from=None: initial title at registration.
TRANSITIONS = frozenset({
    (ORIGIN, "CLEAN", "NPC_GENERATED"),
    (ORIGIN, "CLEAN", "LSAX_LEGAL_DELIVERY"),
    (ORIGIN, "CLEAN", "LEGACY_TRUSTED_IMPORT"),        # only via a probe-proven rule; the rule set is empty
    (ORIGIN, "UNKNOWN", "FIRST_OBSERVED"),
    (ORIGIN, "UNKNOWN", "FIRST_RUN_IMPORT"),
    (ORIGIN, "STOLEN", "OBSERVED_THEFT"),
    ("UNKNOWN", "STOLEN", "STOLEN_RECORD_MATCH"),
    ("UNKNOWN", "UNDERGROUND", "UNDERGROUND_TRADE"),
    ("CLEAN", "STOLEN", "TAKEN_WITHOUT_TRANSACTION"),
    ("SALVAGE", "STOLEN", "TAKEN_WITHOUT_TRANSACTION"),
    ("RECOVERED", "STOLEN", "TAKEN_WITHOUT_TRANSACTION"),
    ("STOLEN", "RECOVERED", "RETURNED_TO_RIGHTFUL_OWNER"),
    ("STOLEN", "UNDERGROUND", "UNDERGROUND_TRADE"),
    ("CLEAN", "SALVAGE", "STRUCTURAL_REPAIR"),
    ("RECOVERED", "SALVAGE", "STRUCTURAL_REPAIR"),
    ("UNDERGROUND", "UNDERGROUND", "UNDERGROUND_TRADE"),
})
POSITIVE_ORIGINS = frozenset({"NPC_GENERATED", "LSAX_LEGAL_DELIVERY", "LEGACY_TRUSTED_IMPORT"})

# Normative: EMPTY until P-ID-01 (or a successor probe) proves an ownership marker that trainers, theft and
# garage storage cannot reproduce. Adding a rule requires runtime evidence + a new independent review.
LEGACY_TRUSTED_RULES = ()


@dataclass(frozen=True)
class WorldVehicle:
    """What LSAX can observe at first run. `source` is ground truth, invisible to LSAX."""
    source: str
    model: int
    plate: str
    mission_entity: bool = False
    in_player_garage: bool = False
    player_opt_in: bool = False
    addon_model: bool = False
    proven_marker: bool = False        # a runtime-proven, unspoofable ownership marker (none exists today)


def classify_import(v, rules=LEGACY_TRUSTED_RULES):
    """First-run import. Returns (action, title, cause). Opt-in is recorded as history only."""
    if v.mission_entity:
        return "EXCLUDED", None, "MISSION_OR_SCRIPT_OWNED"
    for name, rule in rules:
        if rule(v):
            return "REGISTER", "CLEAN", "LEGACY_TRUSTED_IMPORT:" + name
    return "REGISTER", "UNKNOWN", "FIRST_RUN_IMPORT"


def reachable_from(start_titles):
    seen, q = set(start_titles), deque(start_titles)
    while q:
        t = q.popleft()
        for f, to, _ in TRANSITIONS:
            if f == t and to not in seen:
                seen.add(to)
                q.append(to)
    return seen


def main():
    ok = "CLEAN" not in reachable_from(["UNKNOWN"]) and "CLEAN" not in reachable_from(["STOLEN"]) \
        and "CLEAN" not in reachable_from(["UNDERGROUND"])
    into_clean = {c for f, to, c in TRANSITIONS if to == "CLEAN"}
    ok &= into_clean <= POSITIVE_ORIGINS and all(f is ORIGIN for f, to, _ in TRANSITIONS if to == "CLEAN")
    ok &= LEGACY_TRUSTED_RULES == ()
    print("no path UNKNOWN/STOLEN/UNDERGROUND -> CLEAN; CLEAN only from positive origins; LEGACY_TRUSTED empty:", ok)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
