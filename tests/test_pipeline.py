"""Integration tests with the real model and demo footage.

They need the trained weights (models/best.pt), the demo clips (data/demo) and, for the dataset checks, the processed
dataset (data/processed/merged_shwd). Whatever is missing is skipped with a reason, so the suite also runs on a clean
CPU machine (CI), where only the unit tests and watchdog drills execute.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
DATA = ROOT / "data" / "processed" / "merged_shwd"

pytestmark = pytest.mark.integration
pytest.importorskip("ultralytics", reason="integration tests need the full runtime (requirements.txt)")
if not (ROOT / "models" / "best.pt").exists():
    pytest.skip("integration tests need the trained weights at models/best.pt (see models/README.md)", allow_module_level=True)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from database.database import IncidentDB  # noqa: E402
from inference.detector import Detector  # noqa: E402
from inference.tracker import Pipeline, load_config, process_video  # noqa: E402

needs_data = pytest.mark.skipif(not DATA.exists(), reason="needs the processed dataset in data/processed/merged_shwd")
needs_clips = pytest.mark.skipif(not (DEMO / "track_work_day.mp4").exists() or not (DEMO / "helmet_put_on.mp4").exists(),
                                 reason="needs the demo clips in data/demo (see data/README.md)")


@pytest.fixture(scope="module")
def detector():
    return Detector()


@needs_data
def test_dataset_layout_and_labels():
    d = yaml.safe_load((DATA / "dataset.yaml").read_text())
    assert list(d["names"].values()) == ["person", "helmet", "no_helmet"]
    for s in ("train", "val", "test"):
        imgs = list((DATA / "images" / s).iterdir())
        assert imgs and all((DATA / "labels" / s / f"{p.stem}.txt").exists() for p in imgs)


@needs_data
def test_no_shwd_in_val_or_test():
    for s in ("val", "test"):
        assert not list((DATA / "images" / s).glob("shwd_*"))


@needs_data
def test_official_test_images_untouched():
    assert len(list((DATA / "images" / "test").glob("cppe_*"))) == 141


def test_model_loads_with_expected_classes(detector):
    assert list(detector.names.values()) == ["person", "helmet", "no_helmet"]


@needs_data
def test_image_inference_is_well_formed(detector):
    im = cv2.imread(str(next((DATA / "images" / "val").glob("cppe_*"))))
    persons, heads = detector.track(im)
    for _, box, conf in persons:
        assert box[2] > box[0] and box[3] > box[1] and 0 < conf <= 1
    assert all(h.cls in ("helmet", "no_helmet") for h in heads)


def test_blank_frame_gives_no_detections_and_no_crash(detector):
    detector.reset()
    assert detector.track(np.zeros((720, 1280, 3), np.uint8)) == ([], [])


@needs_clips
def test_zone_incident_end_to_end(tmp_path):
    db = IncidentDB(tmp_path / "t.db")
    cfg = load_config()
    res = process_video(DEMO / "track_work_day.mp4", cfg=cfg, camera_id="track_work_day", db=db, out_path=tmp_path / "o.mp4")
    rows = db.rows()
    assert res["frames"] > 300
    assert any(r["incident_type"] == "ZONE_INTRUSION" for r in rows)
    assert all(Path(r["evidence_path"]).exists() and r["status"] == "CLOSED" for r in rows)
    keys = [(r["incident_type"], r["worker_id"], r["zone"]) for r in rows]
    assert len(keys) == len(set(keys))  # short clip below the cooldown: one incident per worker and zone at most
    assert (tmp_path / "o.mp4").stat().st_size > 10000
    assert len(db.sessions()) == 1


@needs_clips
def test_no_helmet_incident_from_bare_head_footage(tmp_path):
    db = IncidentDB(tmp_path / "t.db")
    process_video(DEMO / "helmet_put_on.mp4", cfg=load_config(), camera_id="helmet_put_on", db=db)
    assert any(r["incident_type"] == "NO_HELMET" for r in db.rows())


def test_resolution_change_keeps_zone(detector):
    z = [{"name": "Z", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    p = Pipeline(detector, 25, load_config(), "x", zones=z, db=IncidentDB(":memory:"))
    assert p.zones.zones[0].pixels(640, 480).max() == 640


def test_dashboard_starts():
    p = subprocess.Popen([sys.executable, str(ROOT / "launch.py"), "--server.headless", "true", "--server.port", "8599"],
                         cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            time.sleep(1)
            try:
                if urllib.request.urlopen("http://localhost:8599/_stcore/health", timeout=2).read() == b"ok":
                    return
            except OSError:
                pass
        pytest.fail("dashboard did not answer")
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


@needs_clips
def test_demo_manifest_files_exist():
    for c in json.loads((DEMO / "demo_clips.json").read_text(encoding="utf-8")):
        assert (DEMO / c["file"]).exists() and c["license"]
