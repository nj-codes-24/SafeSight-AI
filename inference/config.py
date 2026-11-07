"""Runtime settings shared by the pipeline and the dashboard. Free of torch so the dashboard opens quickly."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "models" / "runtime_config.json"
DEFAULTS = {"person_conf": 0.35, "ppe_conf": 0.30, "no_helmet_conf": 0.60, "confirm_seconds": 0.5, "cooldown_seconds": 30.0,
            "lost_track_seconds": 2.0, "zones": {},
            # Incident lifecycle (inference/incident_lifecycle.py). Chosen from first principles, not tuned on evaluation
            # labels: grace covers short occlusions (a third of the cooldown); resolution needs four times the confirmation
            # time, because helmet votes count from the lower PPE threshold; bursts batch notifications, never incidents.
            "grace_seconds": 10.0, "resolve_seconds": 2.0, "burst_seconds": 10.0,
            "edge_margin_px": 2.0}  # a head box this close to the top, left or right border is cut off by the frame


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=1))
