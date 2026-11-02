"""Runtime settings shared by the pipeline and the dashboard. Free of torch so the dashboard opens quickly."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "models" / "runtime_config.json"
DEFAULTS = {"person_conf": 0.35, "ppe_conf": 0.30, "no_helmet_conf": 0.60, "confirm_seconds": 0.5, "cooldown_seconds": 30.0,
            "lost_track_seconds": 2.0, "zones": {}}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=1))
