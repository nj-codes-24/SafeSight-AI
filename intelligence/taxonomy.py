"""Hazard taxonomy: what SafeSight can report, which energy is involved, how severe it can be, and whether it is built.

Severity is the worst credible outcome on a 1-5 scale (5 = fatality likely). It belongs to the hazard and its context,
never to a model's confidence. Codes are stable identifiers: a retired code is never reused for a different hazard.
Status "built" means the logic exists, not that it has been validated on a site (docs/product_research/09).
"""
from dataclasses import dataclass

# Energy sources as in energy-based safety practice (EEI / CSRA high-energy control assessments).
GRAVITY, MOTION, MECHANICAL, ELECTRICAL, THERMAL, CHEMICAL, NONE = (
    "gravity", "motion", "mechanical", "electrical", "thermal", "chemical", "none")
ENERGIES = {GRAVITY, MOTION, MECHANICAL, ELECTRICAL, THERMAL, CHEMICAL, NONE}

BUILT, PLANNED, RESEARCH, INTEGRATION = "built", "planned", "research", "integration"
STATUSES = {BUILT, PLANNED, RESEARCH, INTEGRATION}
SENSING = {"camera", "thermal", "sensor", "integration", "human"}

# Incident types raised by the current pipeline (inference/incident_manager.py).
NO_HELMET, ZONE_INTRUSION = "NO_HELMET", "ZONE_INTRUSION"


@dataclass(frozen=True)
class Hazard:
    code: str
    name: str
    energy: str
    severity: int  # default worst credible outcome, 1-5; a site policy may override it
    sensing: tuple
    status: str
    evidence: str  # what must be observed (or known) before the hazard may be asserted


HAZARDS = {h.code: h for h in [
    Hazard("PPE.HEAD.MISSING", "Head protection missing", GRAVITY, 3, ("camera",), BUILT,
           "head visible for the confirmation time with no hard hat; caps, hoods and religious headwear are not hard hats"),
    Hazard("ZONE.ENTRY", "Restricted area entry", NONE, 3, ("camera",), BUILT,
           "foot point inside the zone polygon for the confirmation time"),
    Hazard("MACH.ZONE.ENTRY", "Person in machine exclusion zone", MECHANICAL, 5, ("camera", "integration"), BUILT,
           "person in the zone; whether the machine is live needs machine-state integration"),
    Hazard("LOAD.SUSPENDED.UNDER", "Person under suspended load", GRAVITY, 5, ("camera", "integration"), BUILT,
           "person in a zone drawn under the lift path; load presence needs crane data or a load detector"),
    Hazard("ELEC.APPROACH", "Approach to energised equipment", ELECTRICAL, 5, ("camera", "integration"), BUILT,
           "person inside an approach boundary drawn by the site; energised state needs integration"),
    Hazard("CONFINED.ENTRY", "Confined-space entry", CHEMICAL, 5, ("camera", "sensor", "integration"), BUILT,
           "entry into the zone at the opening; atmosphere and permit need sensors and integration"),
    Hazard("HOTWORK.AREA.ENTRY", "Hot-work area entry", THERMAL, 4, ("camera", "integration"), BUILT,
           "person in the hot-work zone; permit status needs integration"),
    Hazard("VEH.PED_ZONE.ENTRY", "Pedestrian in vehicle-only area", MOTION, 4, ("camera",), BUILT,
           "person foot point in a vehicle-only zone"),
    Hazard("EDGE.EXPOSURE", "Person at unprotected edge or excavation", GRAVITY, 5, ("camera",), BUILT,
           "person in a zone drawn along the edge; whether edge protection exists needs inspection"),
    Hazard("PPE.HIVIS.MISSING", "High-visibility clothing missing", MOTION, 3, ("camera",), PLANNED,
           "torso visible for the confirmation time without hi-vis colours or bands"),
    Hazard("VEH.PED.CONFLICT", "Vehicle-pedestrian conflict", MOTION, 5, ("camera",), PLANNED,
           "both tracked on a calibrated ground plane; time-to-collision or post-encroachment time below threshold"),
    Hazard("VEH.IN_PED_ZONE", "Vehicle in pedestrian-only area", MOTION, 4, ("camera",), PLANNED,
           "vehicle footprint inside a pedestrian-only zone"),
    Hazard("EGRESS.BLOCKED", "Emergency exit or equipment blocked", NONE, 3, ("camera",), PLANNED,
           "static object inside a keep-clear zone for longer than the dwell time"),
    Hazard("PERSON.DOWN", "Possible person down", NONE, 4, ("camera",), RESEARCH,
           "horizontal body and no movement for the dwell time; a person must confirm"),
    Hazard("PPE.FACE.MISSING", "Face or eye protection missing at a station", CHEMICAL, 3, ("camera",), PLANNED,
           "face visible at close range at a defined station"),
    Hazard("ERGO.POSTURE", "Awkward posture or repetitive lifting (screening)", MECHANICAL, 2, ("camera",), RESEARCH,
           "pose over repeated cycles; a screening trend for a task, never an individual score"),
    Hazard("FIRE.SMOKE.VISIBLE", "Visible smoke or flame (supplemental)", THERMAL, 5, ("camera", "thermal"), RESEARCH,
           "visible smoke or flame; never a substitute for listed fire detection"),
    Hazard("SPILL.VISIBLE", "Visible spill or leak", CHEMICAL, 3, ("camera", "thermal"), RESEARCH,
           "liquid on the floor distinguishable from the floor; RGB alone is unreliable"),
    Hazard("HARNESS.MISSING", "Fall-arrest harness missing at height", GRAVITY, 5, ("camera",), RESEARCH,
           "harness straps visible on the torso; being tied off cannot be confirmed from video"),
    Hazard("GAS.ATMOSPHERE", "Hazardous atmosphere", CHEMICAL, 5, ("sensor",), INTEGRATION,
           "gas detector reading; never inferred from RGB video"),
    Hazard("LOTO.NOT_APPLIED", "Hazardous energy not isolated", MECHANICAL, 5, ("integration", "human"), INTEGRATION,
           "machine-state and permit records; a visible lock does not prove isolation"),
]}


@dataclass(frozen=True)
class ZoneKind:
    kind: str
    person_entry: str | None  # hazard raised when a person enters; None when person entry is not the hazard
    description: str


ZONE_KINDS = {k.kind: k for k in [
    ZoneKind("restricted", "ZONE.ENTRY", "Any person entry is reported (the original behaviour)"),
    ZoneKind("machine_exclusion", "MACH.ZONE.ENTRY", "Machine or robot cell; severity depends on machine state"),
    ZoneKind("suspended_load", "LOAD.SUSPENDED.UNDER", "Area under a lift path"),
    ZoneKind("electrical", "ELEC.APPROACH", "Approach boundary around energised equipment"),
    ZoneKind("confined_space", "CONFINED.ENTRY", "Opening of a confined space"),
    ZoneKind("hot_work", "HOTWORK.AREA.ENTRY", "Hot-work area"),
    ZoneKind("vehicle_only", "VEH.PED_ZONE.ENTRY", "Vehicle aisle or roadway where pedestrians are not allowed"),
    ZoneKind("excavation", "EDGE.EXPOSURE", "Excavation edge"),
    ZoneKind("edge", "EDGE.EXPOSURE", "Unprotected edge or opening"),
    ZoneKind("pedestrian_only", None, "Walkway; the hazard is a vehicle entering (planned), not a person"),
    ZoneKind("keep_clear", None, "Exit route or emergency equipment; the hazard is an obstruction (planned), not a person"),
    ZoneKind("work_area", None, "Area named by a PPE requirement (intelligence/ppe_policy.py); entering it is not a hazard"),
]}
DEFAULT_ZONE_KIND = "restricted"


def validate_kind(kind) -> str:
    """Unknown kinds are rejected, so a typo cannot silently turn an electrical zone into a generic one."""
    kind = kind or DEFAULT_ZONE_KIND
    if kind not in ZONE_KINDS:
        raise ValueError(f"unknown zone kind {kind!r}; expected one of {', '.join(sorted(ZONE_KINDS))}")
    return kind


def hazard_for(incident_type: str, zone_kind: str | None = None) -> Hazard:
    """Taxonomy entry for an incident raised by the pipeline, or for a hazard code given directly."""
    if incident_type == NO_HELMET:
        return HAZARDS["PPE.HEAD.MISSING"]
    if incident_type == ZONE_INTRUSION:
        code = ZONE_KINDS[validate_kind(zone_kind)].person_entry
        if code is None:
            raise ValueError(f"zone kind {zone_kind!r} does not report person entry")
        return HAZARDS[code]
    if incident_type in HAZARDS:
        return HAZARDS[incident_type]
    raise KeyError(f"no hazard for incident type {incident_type!r}")
