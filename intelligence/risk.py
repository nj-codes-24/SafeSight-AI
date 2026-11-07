"""Risk policy engine: turns a hazard event into an explainable risk assessment.

- Risk level is read from a severity x exposure matrix that competent safety personnel own and approve.
- Severity comes from the hazard, then site overrides, then context. Model confidence never lowers risk: it only sets the
  evidence quality, which decides whether a person must confirm the event before anyone is notified.
- Unknown context never lowers risk. A context rule may lower severity only for a value that is known, and only when the
  policy is approved; in a draft policy the reduction is reported but not applied.
- Every assessment records the policy version and status, so evidence always shows which rules produced it.
"""
import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from intelligence.taxonomy import HAZARDS, NONE

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "models" / "risk_policy.json"  # optional site policy; the default below applies when it is absent
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

DEFAULT_POLICY = {
    "version": "default-0.1",
    "status": "draft",
    "approved_by": None,
    "approved_on": None,
    "note": "Example policy shipped with SafeSight. Not validated for any site: a competent person must review and approve it.",
    "exposure_bands_s": [10, 60, 300],  # band 1 below 10 s, band 2 below 60 s, band 3 below 300 s, band 4 above
    "matrix": {
        "1": ["LOW", "LOW", "LOW", "MEDIUM"],
        "2": ["LOW", "LOW", "MEDIUM", "MEDIUM"],
        "3": ["LOW", "MEDIUM", "MEDIUM", "HIGH"],
        "4": ["MEDIUM", "HIGH", "HIGH", "CRITICAL"],
        "5": ["HIGH", "CRITICAL", "CRITICAL", "CRITICAL"],
    },
    "severity": {},  # hazard code -> severity for this site
    "zone_severity": {},  # zone name -> severity for this site (for example a press cell that is always live)
    "context": [
        {"when": {"machine_state": "running"}, "hazards": ["MACH.ZONE.ENTRY"], "severity_delta": 0,
         "reason": "machine reported running"},
        {"when": {"machine_state": "locked_out"}, "hazards": ["MACH.ZONE.ENTRY"], "severity_delta": -3,
         "reason": "machine reported locked out by the control system"},
        {"when": {"load_suspended": True}, "hazards": ["LOAD.SUSPENDED.UNDER"], "severity_delta": 0,
         "reason": "load reported suspended"},
    ],
    "evidence": {"strong": 0.75, "moderate": 0.5},  # detector score bands; below "moderate" the evidence is weak
    "actions": {
        "LOW": ["log"],
        "MEDIUM": ["log", "notify_area_supervisor"],
        "HIGH": ["log", "notify_area_supervisor", "notify_safety_officer"],
        "CRITICAL": ["log", "notify_area_supervisor", "notify_safety_officer", "escalate_if_unacknowledged"],
    },
}


@dataclass
class Assessment:
    hazard: str
    severity: int
    exposure_s: float
    exposure_band: int
    level: str
    evidence: str
    requires_review: bool
    actions: list
    factors: list = field(default_factory=list)
    policy_version: str = ""
    policy_status: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def validate_policy(policy: dict) -> dict:
    """Return a checked copy of the policy, or raise ValueError naming the first problem."""
    p = copy.deepcopy(policy)
    for key in ("version", "status", "exposure_bands_s", "matrix", "evidence", "actions"):
        if key not in p:
            raise ValueError(f"policy is missing {key!r}")
    p.setdefault("severity", {})
    p.setdefault("zone_severity", {})
    p.setdefault("context", [])
    if p["status"] not in ("draft", "approved"):
        raise ValueError("policy status must be 'draft' or 'approved'")
    if p["status"] == "approved" and not (p.get("approved_by") and p.get("approved_on")):
        raise ValueError("an approved policy needs approved_by and approved_on")
    bands = p["exposure_bands_s"]
    if not bands or any(b <= 0 for b in bands) or bands != sorted(set(bands)):
        raise ValueError("exposure_bands_s must be positive and strictly increasing")
    rows = []
    for s in range(1, 6):
        row = p["matrix"].get(str(s))
        if row is None or len(row) != len(bands) + 1 or any(v not in LEVELS for v in row):
            raise ValueError(f"matrix row for severity {s} needs {len(bands) + 1} levels from {LEVELS}")
        rows.append([LEVELS.index(v) for v in row])
    # Risk may never fall when exposure grows or when severity grows.
    if any(r[i] > r[i + 1] for r in rows for i in range(len(r) - 1)) or \
            any(rows[s][i] > rows[s + 1][i] for s in range(4) for i in range(len(bands) + 1)):
        raise ValueError("matrix must not decrease with longer exposure or higher severity")
    for code, s in p["severity"].items():
        if code not in HAZARDS:
            raise ValueError(f"unknown hazard code {code!r} in severity overrides")
        if s not in range(1, 6):
            raise ValueError(f"severity for {code} must be 1-5")
    for zone, s in p["zone_severity"].items():
        if s not in range(1, 6):
            raise ValueError(f"severity for zone {zone!r} must be 1-5")
    for rule in p["context"]:
        if not rule.get("when") or not isinstance(rule["when"], dict):
            raise ValueError("each context rule needs a 'when' mapping")
        if any(c not in HAZARDS for c in rule.get("hazards", [])):
            raise ValueError(f"unknown hazard code in context rule {rule['when']}")
        if rule.get("severity_delta", 0) not in range(-4, 5):
            raise ValueError("severity_delta must be between -4 and 4")
    ev = p["evidence"]
    if not 0 < ev.get("moderate", 0) < ev.get("strong", 0) <= 1:
        raise ValueError("evidence thresholds need 0 < moderate < strong <= 1")
    if set(p["actions"]) - set(LEVELS):
        raise ValueError(f"actions may only be given for {LEVELS}")
    return p


def load_policy(path=POLICY_PATH) -> dict:
    path = Path(path)
    return validate_policy(json.loads(path.read_text(encoding="utf-8")) if path.exists() else DEFAULT_POLICY)


class RiskEngine:
    def __init__(self, policy: dict | None = None):
        self.policy = validate_policy(policy if policy is not None else DEFAULT_POLICY)

    @property
    def approved(self) -> bool:
        return self.policy["status"] == "approved"

    def band(self, exposure_s: float) -> int:
        return 1 + sum(exposure_s >= b for b in self.policy["exposure_bands_s"])

    def evidence(self, score) -> str:
        if score is None:
            return "unknown"
        ev = self.policy["evidence"]
        return "strong" if score >= ev["strong"] else "moderate" if score >= ev["moderate"] else "weak"

    def assess(self, hazard_code: str, exposure_s: float = 0.0, score=None, zone: str | None = None,
               context: dict | None = None) -> Assessment:
        hazard = HAZARDS[hazard_code]
        p, context = self.policy, context or {}
        energy = f" ({hazard.energy} energy)" if hazard.energy != NONE else ""
        severity, factors = hazard.severity, [f"{hazard.name}: default severity {hazard.severity}{energy}"]
        if hazard_code in p["severity"]:
            severity = p["severity"][hazard_code]
            factors.append(f"site policy sets severity {severity}")
        if zone is not None and zone in p["zone_severity"]:
            severity = p["zone_severity"][zone]
            factors.append(f"zone '{zone}' set to severity {severity}")
        for rule in p["context"]:
            if rule.get("hazards") and hazard_code not in rule["hazards"]:
                continue
            if not all(k in context and context[k] == v for k, v in rule["when"].items()):
                continue  # unknown or different context: the rule does not apply, so it cannot lower risk
            delta = rule.get("severity_delta", 0)
            reason = rule.get("reason", str(rule["when"]))
            if delta < 0 and not self.approved:
                factors.append(f"{reason}: would lower severity by {-delta}, not applied because the policy is a draft")
                continue
            if delta:
                severity = min(5, max(1, severity + delta))
                factors.append(f"{reason}: severity {'+' if delta > 0 else ''}{delta} -> {severity}")
            else:
                factors.append(reason)
        band = self.band(exposure_s)
        level = p["matrix"][str(severity)][band - 1]
        factors.append(f"exposure {exposure_s:.1f} s (band {band}) -> {level}")
        evidence = self.evidence(score)
        review = evidence in ("weak", "unknown")
        if review:
            factors.append(f"evidence {evidence}: a person should confirm before notification")
        return Assessment(hazard_code, severity, round(float(exposure_s), 2), band, level, evidence, review,
                          list(p["actions"].get(level, [])), factors, p["version"], p["status"])

    def escalated(self, before: Assessment, after: Assessment) -> bool:
        return LEVELS.index(after.level) > LEVELS.index(before.level)
