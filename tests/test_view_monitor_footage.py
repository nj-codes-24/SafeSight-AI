"""Camera view monitoring on the bundled demo footage (skipped when the clips are absent).

The footage is real; the camera changes applied to it are SIMULATED (crop shifts, splicing two clips, covering the
frame). framing_bare_head is the only demo clip from a tripod-steady camera; the other "static" clips are hand-held
stock footage that drifts 2-5 % of the frame width (measured in docs/product_research/21_CAMERA_VIEW_CHANGE_DETECTION.md),
and ballast_train is filmed from a moving camera. No physical camera was moved for these tests.
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from inference import view_monitor as vm

pytestmark = pytest.mark.integration
DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"
CLIPS = ("framing_bare_head", "helmet_put_on", "ballast_train")
if not all((DEMO / f"{c}.mp4").exists() for c in CLIPS):
    pytest.skip("needs the demo clips in data/demo", allow_module_level=True)


def frames(clip, limit=None):
    cap = cv2.VideoCapture(str(DEMO / f"{clip}.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    out = []
    while limit is None or len(out) < limit:
        ok, f = cap.read()
        if not ok:
            break
        out.append(f)
    cap.release()
    return out, fps


@pytest.fixture(scope="module")
def steady():
    return frames("framing_bare_head")


def run(seq, fps, discontinuities=()):
    m, trs = vm.ViewMonitor(), []
    for i, f in enumerate(seq):
        t = i / fps
        if m.due(t, i in discontinuities):
            trs += m.observe(f, t, i in discontinuities)
    return m, trs


def shifted(f, dx):
    """Simulated pan: the frame content moves left by dx pixels (the camera turned right); the edge is replicated."""
    return cv2.warpAffine(f, np.float32([[1, 0, -dx], [0, 1, 0]]), f.shape[1::-1], borderMode=cv2.BORDER_REPLICATE)


def test_real_workers_in_a_steady_clip_played_twice_are_no_view_change(steady):
    seq, fps = steady
    m, trs = run(seq + seq, fps, discontinuities={len(seq)})  # a looping file restarting
    assert [tr.state for tr in trs] == [vm.VIEW_STABLE] and m.disturbances == 0


def test_simulated_pan_on_real_footage_is_detected(steady):
    seq, fps = steady
    w = seq[0].shape[1]
    moved = [shifted(f, int(0.12 * w)) for f in seq]  # 12 % of the width
    m, trs = run(seq[:72] + moved + moved, fps)  # 3 s as filmed, then the camera turned
    (tr,) = [x for x in trs if x.kind]
    assert tr.kind == vm.CAMERA_VIEW_CHANGED and tr.evidence["transform"]["movement"][0] == "pan"
    assert tr.evidence["transform"]["dx"] == pytest.approx(0.12, abs=0.01)


def test_cut_to_another_real_scene_is_a_scene_switch(steady):
    seq, fps = steady
    other, _ = frames("helmet_put_on")
    m, trs = run(seq[:120] + other, fps)
    assert [x.kind for x in trs if x.kind] == [vm.CAMERA_SCENE_SWITCHED]


def test_cut_to_a_moving_camera_is_detected(steady):
    seq, fps = steady
    moving, _ = frames("ballast_train", 300)
    m, trs = run(seq[:120] + moving, fps)
    assert [x.kind for x in trs if x.kind] == [vm.CAMERA_SCENE_SWITCHED] and not m.trusted


def test_covering_a_real_scene_is_blocked(steady):
    seq, fps = steady
    dark = np.full_like(seq[0], 20)
    m, trs = run(seq[:120] + [dark] * 200, fps)
    assert [x.kind for x in trs if x.kind] == [vm.CAMERA_BLOCKED]


def test_a_moving_camera_never_gets_a_reference(steady):
    moving, fps = frames("ballast_train")  # 20.6 s, filmed from a moving camera
    m, trs = run(moving, fps)
    assert m.reference is None and m.bootstrapping and trs == []
    assert any(w.startswith("no steady view") for w in m.warnings)
