"""Runtime configuration: load YAML or JSON, validate all of it before anything starts, and keep secrets out of it.

Relative paths are resolved against the SafeSight project root (the folder that contains runtime/), whatever the
current directory. Unknown keys are errors, so a typo can never silently disable a setting. Camera credentials are
never part of the configuration: RTSP sources name environment variables instead (runtime/sources.py).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from inference.config import DEFAULTS as PIPELINE_DEFAULTS
from inference.view_monitor import ViewSettings
from inference.zone_monitor import validate_polygon
from intelligence.taxonomy import validate_kind

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
BACKENDS = ("batched", "shared", "per_camera", "null")
OVERRIDABLE = {k for k in PIPELINE_DEFAULTS if k != "zones"}  # thresholds and timings a camera may override
VALIDATED_NO_HELMET = 0.60  # application threshold from the final evaluation; other values are allowed but logged


class ConfigError(ValueError):
    pass


@dataclass
class Processing:
    max_fps: float | None = 10.0  # analysis rate cap; None processes every frame the source delivers
    queue_size: int = 2
    annotate: bool = False  # draw boxes only on evidence frames


@dataclass
class Reconnect:
    max_attempts: int = 10  # consecutive failed attempts before the camera goes to ERROR; 0 retries forever
    initial_delay_s: float = 1.0
    max_delay_s: float = 30.0


@dataclass
class Health:
    # A camera analysing well below its configured rate is not monitoring as configured: report it, do not hide it.
    degraded_ratio: float = 0.8  # processed rate below this share of the target rate is DEGRADED
    max_drop_ratio: float = 0.2  # share of selected frames dropped under backpressure above which it is DEGRADED
    stall_s: float = 5.0  # no processed frame for this long while streaming is DEGRADED
    window_s: float = 10.0
    warmup_s: float = 5.0


@dataclass
class Camera:
    id: str
    name: str
    site: str | None
    enabled: bool
    source: dict
    zones: list
    overrides: dict
    processing: Processing
    reconnect: Reconnect
    health: Health
    view: ViewSettings = field(default_factory=ViewSettings)  # camera view monitoring (inference/view_monitor.py)


@dataclass
class Inference:
    backend: str = "batched"
    weights: Path = ROOT / "models" / "best.pt"
    imgsz: int = 640
    device: str = "auto"
    max_batch: int = 8
    batch_wait_ms: float = 5.0
    timeout_s: float = 30.0


@dataclass
class RuntimeConfig:
    database: Path
    evidence_dir: Path
    status_file: Path
    log_file: Path | None
    log_level: str
    status_interval_s: float
    risk_policy: Path | None
    pipeline_config: Path
    inference: Inference
    sites: dict = field(default_factory=dict)  # id -> name
    cameras: list = field(default_factory=list)
    ppe_policy: Path | None = None  # intelligence/ppe_policy.py file; absent means every PPE requirement is unconfigured

    def camera(self, camera_id) -> Camera:
        return next(c for c in self.cameras if c.id == camera_id)


def _path(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def _only(d, allowed, where) -> dict:
    if d is None:
        return {}
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: expected a mapping")
    extra = set(d) - set(allowed)
    if extra:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(sorted(extra))}; allowed: {', '.join(sorted(allowed))}")
    return d


def _num(v, where, lo, hi, integer=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and int(v) != v) or not lo <= v <= hi:
        raise ConfigError(f"{where}: must be {'an integer' if integer else 'a number'} between {lo} and {hi}")
    return int(v) if integer else float(v)


def _block(cls, d, where, ranges):
    d = _only(d, cls.__dataclass_fields__, where)
    out = {}
    for k, v in d.items():
        if k in ranges:
            lo, hi, integer = ranges[k]
            out[k] = None if v is None and k == "max_fps" else _num(v, f"{where}.{k}", lo, hi, integer)
        else:
            if not isinstance(v, bool):
                raise ConfigError(f"{where}.{k}: must be true or false")
            out[k] = v
    return out


PROCESSING_RANGES = {"max_fps": (0.2, 120, False), "queue_size": (1, 64, True)}
RECONNECT_RANGES = {"max_attempts": (0, 10_000, True), "initial_delay_s": (0.01, 600, False), "max_delay_s": (0.01, 3600, False)}
HEALTH_RANGES = {"degraded_ratio": (0, 1, False), "max_drop_ratio": (0, 1, False), "stall_s": (0.1, 3600, False),
                 "window_s": (1, 3600, False), "warmup_s": (0, 3600, False)}
VIEW_RANGES = {"check_interval_s": (0.05, 60, False), "width": (96, 1280, True), "init_s": (0, 600, False),
               "confirm_s": (0.5, 600, False), "blocked_confirm_s": (0.5, 600, False), "recover_s": (0.5, 600, False),
               "unverified_after_s": (1, 3600, False), "max_shift": (0.002, 0.5, False), "min_inliers": (6, 500, True),
               "blank_std": (0, 64, False), "structure_ratio": (0, 1, False), "min_features": (0, 300, True), "min_reference_std": (0, 128, False), "focus_ratio": (0, 1, False),
               "jitter_shift": (0, 0.5, False)}
# A test pattern has no scene to verify; every real source is checked unless its configuration says otherwise
VIEW_ENABLED_BY_DEFAULT = {"file": True, "rtsp": True, "synthetic": False}


def _zones(z, where, app_zones, zones_from):
    if zones_from is not None:
        if z:
            raise ConfigError(f"{where}: give either zones or zones_from_app, not both")
        if zones_from not in app_zones:
            raise ConfigError(f"{where}.zones_from_app: no zones for '{zones_from}' in the app configuration")
        z = app_zones[zones_from]
    out, names = [], set()
    for i, zone in enumerate(z or []):
        w = f"{where}.zones[{i}]"
        zone = _only(zone, {"name", "polygon", "kind"}, w)
        if not zone.get("name") or zone["name"] in names:
            raise ConfigError(f"{w}: needs a unique name")
        try:
            out.append({"name": str(zone["name"]), "polygon": validate_polygon(zone.get("polygon") or []),
                        "kind": validate_kind(zone.get("kind"))})
        except (ValueError, TypeError) as e:
            raise ConfigError(f"{w}: {e}") from None
        names.add(zone["name"])
    return out


def parse(data: dict, app_zones: dict | None = None) -> RuntimeConfig:
    """Validate a configuration mapping. app_zones are the dashboard's zones by camera view (zones_from_app)."""
    from runtime.sources import SOURCE_TYPES  # the source classes validate their own options

    data = _only(data, {"runtime", "inference", "sites", "defaults", "cameras"}, "config")
    r = _only(data.get("runtime"), {"database", "evidence_dir", "status_file", "log_file", "log_level", "status_interval_s",
                                    "risk_policy", "pipeline_config", "ppe_policy"}, "runtime")
    ppe_path = _path(r.get("ppe_policy", "config/ppe_policy.json"))
    if r.get("ppe_policy") and not ppe_path.exists():
        raise ConfigError(f"runtime.ppe_policy: file not found: {ppe_path}")
    try:
        from intelligence.ppe_policy import load as load_ppe

        load_ppe(ppe_path)  # validate now, so a broken policy stops the start instead of every camera
    except ValueError as e:
        raise ConfigError(f"runtime.ppe_policy: {e}") from None
    level = str(r.get("log_level", "INFO")).upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ConfigError("runtime.log_level: DEBUG, INFO, WARNING or ERROR")
    inf = _only(data.get("inference"), Inference.__dataclass_fields__, "inference")
    backend = inf.get("backend", "batched")
    if backend not in BACKENDS:
        raise ConfigError(f"inference.backend: one of {', '.join(BACKENDS)}")
    inference = Inference(backend=backend, weights=_path(inf.get("weights", Inference.weights)),
                          imgsz=_num(inf.get("imgsz", 640), "inference.imgsz", 64, 4096, True),
                          device=str(inf.get("device", "auto")),
                          max_batch=_num(inf.get("max_batch", 8), "inference.max_batch", 1, 64, True),
                          batch_wait_ms=_num(inf.get("batch_wait_ms", 5.0), "inference.batch_wait_ms", 0, 1000),
                          timeout_s=_num(inf.get("timeout_s", 30.0), "inference.timeout_s", 0.1, 600))

    sites = {}
    for i, s in enumerate(data.get("sites") or []):
        s = _only(s, {"id", "name"}, f"sites[{i}]")
        if not ID_RE.match(str(s.get("id", ""))) or s["id"] in sites:
            raise ConfigError(f"sites[{i}].id: unique, letters, digits, '-' or '_'")
        sites[s["id"]] = str(s.get("name", s["id"]))

    defaults = _only(data.get("defaults"), {"processing", "reconnect", "health", "view_monitor"}, "defaults")
    dp = _block(Processing, defaults.get("processing"), "defaults.processing", PROCESSING_RANGES)
    dr = _block(Reconnect, defaults.get("reconnect"), "defaults.reconnect", RECONNECT_RANGES)
    dh = _block(Health, defaults.get("health"), "defaults.health", HEALTH_RANGES)
    dv = _block(ViewSettings, defaults.get("view_monitor"), "defaults.view_monitor", VIEW_RANGES)

    cams, ids = [], set()
    for i, c in enumerate(data.get("cameras") or []):
        w = f"cameras[{i}]"
        c = _only(c, {"id", "name", "site", "enabled", "source", "zones", "zones_from_app", "overrides", "processing",
                      "reconnect", "health", "view_monitor"}, w)
        cid = str(c.get("id", ""))
        if not ID_RE.match(cid) or cid in ids:
            raise ConfigError(f"{w}.id: unique, 1-48 letters, digits, '-' or '_'")
        ids.add(cid)
        w = f"camera '{cid}'"
        site = c.get("site")
        if site is not None and sites and site not in sites:
            raise ConfigError(f"{w}.site: '{site}' is not in sites")
        src = _only(c.get("source"), {"type"} | set().union(*(t.OPTIONS for t in SOURCE_TYPES.values())), f"{w}.source")
        kind = src.get("type")
        if kind not in SOURCE_TYPES:
            raise ConfigError(f"{w}.source.type: one of {', '.join(SOURCE_TYPES)}")
        try:
            SOURCE_TYPES[kind].validate({k: v for k, v in src.items() if k != "type"})
        except ValueError as e:
            raise ConfigError(f"{w}.source: {e}") from None
        overrides = _only(c.get("overrides"), OVERRIDABLE, f"{w}.overrides")
        for k, v in overrides.items():
            _num(v, f"{w}.overrides.{k}", 0, 3600)
        zones = _zones(c.get("zones"), w, app_zones or {}, c.get("zones_from_app"))
        view = ViewSettings(**{"enabled": VIEW_ENABLED_BY_DEFAULT[kind], **dv,
                               **_block(ViewSettings, c.get("view_monitor"), f"{w}.view_monitor", VIEW_RANGES)})
        if zones and view.enabled and not view.geometry:
            raise ConfigError(f"{w}.view_monitor.geometry: false (a view that is meant to move) cannot be combined with "
                              "zones: image coordinates of a moving view do not stay on the same place")
        cams.append(Camera(
            id=cid, name=str(c.get("name", cid)), site=site, enabled=bool(c.get("enabled", True)), source=dict(src),
            zones=zones, overrides=overrides,
            processing=Processing(**{**dp, **_block(Processing, c.get("processing"), f"{w}.processing", PROCESSING_RANGES)}),
            reconnect=Reconnect(**{**dr, **_block(Reconnect, c.get("reconnect"), f"{w}.reconnect", RECONNECT_RANGES)}),
            health=Health(**{**dh, **_block(Health, c.get("health"), f"{w}.health", HEALTH_RANGES)}), view=view))
    if not cams:
        raise ConfigError("cameras: at least one camera is required")

    log_file = r.get("log_file", "logs/runtime/runtime.log")
    return RuntimeConfig(
        database=_path(r.get("database", "logs/runtime/incidents.db")),
        evidence_dir=_path(r.get("evidence_dir", "logs/runtime/evidence")),
        status_file=_path(r.get("status_file", "logs/runtime/status.json")),
        log_file=_path(log_file) if log_file else None, log_level=level,
        status_interval_s=_num(r.get("status_interval_s", 2.0), "runtime.status_interval_s", 0.1, 600),
        risk_policy=_path(r["risk_policy"]) if r.get("risk_policy") else None,
        pipeline_config=_path(r.get("pipeline_config", "models/runtime_config.json")),
        inference=inference, sites=sites, cameras=cams, ppe_policy=ppe_path if ppe_path.exists() else None)


def load(path) -> RuntimeConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"configuration file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: cannot parse ({e})") from None
    pipeline_cfg = _path(((data or {}).get("runtime") or {}).get("pipeline_config", "models/runtime_config.json"))
    app_zones = json.loads(pipeline_cfg.read_text()).get("zones", {}) if pipeline_cfg.exists() else {}
    return parse(data or {}, app_zones)


def pipeline_settings(cfg: RuntimeConfig, camera: Camera) -> dict:
    """Thresholds and timings for one camera: the dashboard's saved settings (unchanged), then camera overrides."""
    saved = json.loads(cfg.pipeline_config.read_text()) if cfg.pipeline_config.exists() else {}
    base = {k: saved.get(k, v) for k, v in PIPELINE_DEFAULTS.items() if k != "zones"}
    return {**base, **camera.overrides}
