"""PPE requirement policy: where and when a PPE item is required, as configured by an authorised safety administrator.

SafeSight never infers a legal PPE requirement from the image. A requirement exists only if this policy says so; the
final requirements must be set by competent site safety personnel under the rules and procedures that apply to the
site. The default is conservative in both directions:

- No policy, or no entry for a camera: the requirement is UNCONFIGURED. Missing PPE is reported for review, never as a
  confirmed violation (no false reassurance, no nuisance alarm).
- Entries scoped to zones apply only to workers whose foot point is inside the zone. Outside every required zone the
  requirement is NOT_REQUIRED for that worker, and no PPE violation is raised.
- A worker whose zone membership is uncertain (foot point cut off by the frame, or moving across a boundary) is
  AMBIGUOUS when membership would decide the answer; ambiguity is kept, never resolved by guessing.
- An entry outside its effective period, or with "active": false, is INACTIVE.
- A zone-scoped entry beats a camera-wide one; at the same scope, "required" and "not required" together are a conflict
  and give AMBIGUOUS.

Policy file (JSON), schema safesight.ppe_policy/1.0:

    {"schema": "safesight.ppe_policy/1.0", "version": "site-a-3", "status": "draft",
     "approved_by": null, "approved_on": null,
     "entries": [{"id": "R1", "site": "*", "camera": "dock-1", "zone": "Loading area", "ppe": ["head"],
                  "required": true, "status": "confirmed", "active": true,
                  "effective_from": "2026-11-01T00:00:00+00:00", "effective_to": null,
                  "established_by": "Site safety lead", "basis": "Site rule SR-12"}]}

`status` of an entry: "confirmed" (set by the responsible person) or "provisional" (entered but not yet confirmed).
Only a confirmed entry can make missing PPE a confirmed violation; a provisional entry gives a review item, exactly
like an unconfigured requirement (inference/tracker.py, milestone M3), so a rule nobody authorised never produces an
alert that looks authoritative. The status of the policy document follows the risk policy: "draft" or "approved"
(approved needs approved_by and approved_on). A draft document is used, but every decision carries the document status
and the entry status, so reports can separate them.
"""
import copy
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "ppe_policy.json"  # optional; absent means every requirement is unconfigured
SCHEMA = "safesight.ppe_policy/1.0"
PPE_ITEMS = {"head"}  # PPE categories SafeSight can observe today; others may be configured once detectors exist
FUTURE_ITEMS = {"hi_vis", "footwear", "eye", "hearing", "gloves", "harness"}

REQUIRED, NOT_REQUIRED, UNCONFIGURED, INACTIVE, AMBIGUOUS = "required", "not_required", "unconfigured", "inactive", "ambiguous"


@dataclass(frozen=True)
class Requirement:
    """The answer for one worker, one PPE item, at one time."""
    state: str  # required | not_required | unconfigured | inactive | ambiguous
    status: str | None = None  # entry status when an entry decided it: confirmed | provisional
    entry_id: str | None = None
    zone: str | None = None
    reason: str = ""
    policy_version: str | None = None
    policy_status: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _time(v, where):
    if v is None:
        return None
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError as e:
        raise ValueError(f"{where}: not an ISO 8601 time: {v!r}") from e
    if t.tzinfo is None:
        raise ValueError(f"{where}: times need a UTC offset, e.g. 2026-11-01T00:00:00+00:00")
    return t


def validate(policy: dict) -> dict:
    p = copy.deepcopy(policy)
    if p.get("schema") != SCHEMA:
        raise ValueError(f"PPE policy schema must be {SCHEMA}")
    for k in ("version", "status", "entries"):
        if k not in p:
            raise ValueError(f"PPE policy is missing {k!r}")
    if p["status"] not in ("draft", "approved"):
        raise ValueError("PPE policy status must be 'draft' or 'approved'")
    if p["status"] == "approved" and not (p.get("approved_by") and p.get("approved_on")):
        raise ValueError("an approved PPE policy needs approved_by and approved_on")
    ids = set()
    for i, e in enumerate(p["entries"]):
        w = f"entry {e.get('id', i)}"
        unknown = set(e) - {"id", "site", "camera", "zone", "ppe", "required", "status", "active", "effective_from",
                            "effective_to", "established_by", "basis", "note"}
        if unknown:
            raise ValueError(f"{w}: unknown key(s) {sorted(unknown)}")
        if not e.get("id") or e["id"] in ids:
            raise ValueError(f"{w}: every entry needs a unique id")
        ids.add(e["id"])
        if not e.get("camera"):
            raise ValueError(f"{w}: camera is required ('*' for every camera of the site)")
        items = e.get("ppe") or []
        if not items or set(items) - PPE_ITEMS - FUTURE_ITEMS:
            raise ValueError(f"{w}: ppe must list items from {sorted(PPE_ITEMS | FUTURE_ITEMS)}")
        if not isinstance(e.get("required"), bool):
            raise ValueError(f"{w}: required must be true or false")
        if e.get("status") not in ("confirmed", "provisional"):
            raise ValueError(f"{w}: status must be 'confirmed' or 'provisional'")
        if e["status"] == "confirmed" and not e.get("established_by"):
            raise ValueError(f"{w}: a confirmed entry must name who established it (established_by)")
        a, b = _time(e.get("effective_from"), w), _time(e.get("effective_to"), w)
        if a and b and b <= a:
            raise ValueError(f"{w}: effective_to must be after effective_from")
        e.setdefault("site", "*")
        e.setdefault("zone", None)
        e.setdefault("active", True)
    return p


def load(path=POLICY_PATH) -> dict | None:
    """The site's PPE policy, or None when there is none (every requirement then reads as unconfigured)."""
    path = Path(path)
    return validate(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


class PPEPolicy:
    def __init__(self, policy: dict | None):
        self.policy = validate(policy) if policy is not None else None

    @property
    def configured(self) -> bool:
        return self.policy is not None

    def describe(self) -> dict:
        if self.policy is None:
            return {"version": None, "status": "unconfigured", "entries": 0}
        return {"version": self.policy["version"], "status": self.policy["status"], "entries": len(self.policy["entries"])}

    def requirement(self, item: str, camera: str, site: str | None = None, zones_inside=(), zones_uncertain=(),
                    when: datetime | None = None) -> Requirement:
        """Requirement for one worker. zones_inside: zones the worker is confirmed inside. zones_uncertain: zones whose
        membership cannot be decided now (foot point not visible, or crossing the boundary)."""
        if self.policy is None:
            return Requirement(UNCONFIGURED, reason="no PPE policy configured")
        pv, ps = self.policy["version"], self.policy["status"]
        mine = [e for e in self.policy["entries"] if item in e["ppe"] and e["camera"] in ("*", camera)
                and e["site"] in ("*", site)]
        if not mine:
            return Requirement(UNCONFIGURED, reason=f"no entry for {item} on camera {camera}", policy_version=pv,
                               policy_status=ps)
        now = when or datetime.now(timezone.utc)

        def live(e):
            a, b = _time(e.get("effective_from"), e["id"]), _time(e.get("effective_to"), e["id"])
            return e.get("active", True) and (a is None or now >= a) and (b is None or now < b)

        def decide(entries, zone):
            if not entries:
                return None
            lives = [e for e in entries if live(e)]
            if not lives:
                e = entries[0]
                return Requirement(INACTIVE, e["status"], e["id"], zone, "entry inactive or outside its effective period", pv, ps)
            kinds = {e["required"] for e in lives}
            if len(kinds) > 1:
                return Requirement(AMBIGUOUS, None, ",".join(sorted(e["id"] for e in lives)), zone,
                                   "conflicting entries at the same scope", pv, ps)
            e = sorted(lives, key=lambda x: (x["status"] != "provisional", x["id"]))[0]  # provisional status is reported
            return Requirement(REQUIRED if e["required"] else NOT_REQUIRED, e["status"], e["id"], zone,
                               e.get("basis") or "", pv, ps)

        zoned = [e for e in mine if e["zone"]]
        inside = [e for e in zoned if e["zone"] in set(zones_inside)]
        unsure = [e for e in zoned if e["zone"] in set(zones_uncertain) and e["zone"] not in set(zones_inside)]
        camera_wide = decide([e for e in mine if not e["zone"]], None)
        by_zone = [decide([e for e in inside if e["zone"] == z], z) for z in sorted({e["zone"] for e in inside})]
        by_zone = [r for r in by_zone if r is not None]
        if by_zone:
            states = {r.state for r in by_zone}
            if REQUIRED in states and NOT_REQUIRED in states:
                return Requirement(AMBIGUOUS, None, ",".join(r.entry_id for r in by_zone), None,
                                   "worker inside zones with conflicting requirements", pv, ps)
            decided = next((r for r in by_zone if r.state == REQUIRED), by_zone[0])
        else:
            decided = camera_wide or Requirement(NOT_REQUIRED, None, None, None,
                                                 "outside every zone with an entry for this item", pv, ps)
        if unsure:  # membership of a zone with an entry is unknown: ambiguous if that zone could change the answer
            alt = decide(unsure, unsure[0]["zone"])
            if alt is not None and alt.state != decided.state and alt.state in (REQUIRED, NOT_REQUIRED):
                return Requirement(AMBIGUOUS, None, alt.entry_id, alt.zone, "zone membership uncertain", pv, ps)
        return decided
