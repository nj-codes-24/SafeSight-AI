"""First-pass (PROVISIONAL) labels for the M2 evaluation, written from visual review of timestamped contact sheets and
full-resolution detail crops (scripts/validation/inventory.py, review_frames.py). No model output was drawn on any
review image. These labels are NOT ground truth: an AI annotator made them, without an independent human review.

    python scripts/validation/labels_m2_provisional_v1.py      writes reports/validation/annotations/m2-provisional-v1/*.json

Times are seconds; boundaries from contact sheets carry an uncertainty of at least half the sampling interval.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from intelligence.annotations import SCHEMA, validate  # noqa: E402

SET = "m2-provisional-v1"
OUT = ROOT / "reports" / "validation" / "annotations" / SET
PPE, ZONE = "PPE.HEAD.MISSING", "ZONE.ENTRY"
ANNOTATOR = "ai-first-pass (Claude Opus 5.5)"
BLIND = {
    "development": ("partial", "Model incidents on these clips were seen during M1 runtime testing before labelling."),
    "held-out": ("partial", "No model output for these clips was viewed in this session; the repository's earlier "
                            "unseen-footage notes (aggregate counts per clip) were known."),
}
NO_ZONE = "not evaluable: no zone configured for this clip"


def I(h, a, b, state, note=""):  # noqa: E743
    return {"hazard": h, "start_s": a, "end_s": b, "state": state, "note": note}


def E(eid, h, kind, a, b, ua, ub, worker, obs, req=None, zone=None, frames=(), note=""):
    return {"id": eid, "hazard": h, "kind": kind, "start_s": a, "end_s": b, "start_unc_s": ua, "end_unc_s": ub, "zone": zone,
            "worker": worker, "observability": obs, "requirement": req, "evidence_frames": list(frames), "status": "provisional",
            "annotator": ANNOTATOR, "reviews": [], "note": note}


def ppe_mon(dur, note=""):
    return [I(PPE, 0.0, dur, "monitorable", note)]


CLIPS = {
    "track_work_day": dict(
        intervals=[I(PPE, 0.0, 7.46, "monitorable", "three workers, orange hard hats, heads clear"),
                   I(ZONE, 0.0, 7.46, "monitorable", "feet of all three workers visible")],
        events=[E("track_work_day-E01", ZONE, "violation", 0.0, 7.46, 0.0, 0.0, "left worker, orange suit, shovel", "clear",
                  zone="Live rail", frames=(0, 250, 362),
                  note="Feet inside the zone from the first to the last frame; one foot on the boundary at about 6.25-6.75 s.")],
        people={"distinct_workers": 3, "basis": "static view, all three visible throughout"},
        attributes={"lighting": "day", "distance": "near", "camera": "static", "density": "3", "image_quality": "good"}),
    "roadworks_night": dict(
        intervals=[I(PPE, 0.0, 12.45, "monitorable", "three workers in white hard hats; two transient people at the end"),
                   I(ZONE, 0.0, 12.45, "monitorable")],
        events=[E("roadworks_night-E01", PPE, "uncertain", 5.2, 8.0, 0.5, 0.5, "right worker, blue clothes, yellow vest",
                  "partial", note="Turned away into shadow; headwear not identifiable; leaves frame right."),
                E("roadworks_night-E02", PPE, "not_applicable", 10.3, 12.45, 0.3, 0.0, "pedestrian walking past on the left",
                  "partial", note="Member of the public on the street, not a worker: head protection does not apply."),
                E("roadworks_night-E03", PPE, "uncertain", 10.3, 12.45, 0.3, 0.0, "traffic guard entering on the right",
                  "partial", note="Dark helmet-like headwear, not clearly identifiable."),
                E("roadworks_night-E04", ZONE, "violation", 0.0, 12.45, 0.0, 0.0, "left worker, jackhammer, red vest", "clear",
                  zone="Breaking area", frames=(0, 192, 360)),
                E("roadworks_night-E05", ZONE, "violation", 0.0, 12.45, 0.0, 0.0, "middle worker, light suit, yellow vest",
                  "clear", zone="Breaking area", frames=(0, 192, 360)),
                E("roadworks_night-E06", ZONE, "violation", 0.0, 4.4, 0.0, 0.8, "right worker, blue clothes, yellow vest",
                  "partial", zone="Breaking area", frames=(0, 96),
                  note="Feet hidden behind equipment; exit judged from body position, about 4.4 s.")],
        people={"distinct_workers": 5, "basis": "three workers throughout, a traffic guard and a pedestrian from 10.3 s"},
        attributes={"lighting": "night, floodlit", "distance": "near", "camera": "static", "density": "3-5",
                    "image_quality": "good"}),
    "ballast_train": dict(
        intervals=[I(PPE, 0.0, 6.3, "monitorable", "wagon wheels, no people"),
                   I(PPE, 6.3, 20.64, "uncertain", "rider's head out of frame until about 11.9 s; small background workers "
                                                    "from about 9 s with unclear headwear")],
        events=[],
        people={"distinct_workers": "3-4", "basis": "one rider and two or three background workers"},
        attributes={"lighting": "day", "distance": "near and far", "camera": "moving", "density": "1-4", "image_quality": "good"}),
    "helmet_put_on": dict(
        intervals=ppe_mon(12.25, "close-up of one worker"),
        events=[E("helmet_put_on-E01", PPE, "violation", 0.0, 1.4, 0.0, 0.15, "close-up worker in hi-vis", "clear", "evident",
                  frames=(0, 24),
                  note="Bare head; the worker then puts on a hard hat, which shows it is expected."),
                E("helmet_put_on-E02", PPE, "uncertain", 1.4, 3.8, 0.15, 0.3, "close-up worker in hi-vis", "partial",
                  note="Hard hat being placed: held over the head, partly covering it.")],
        people={"distinct_workers": 1, "basis": "single person"},
        attributes={"lighting": "day", "distance": "near", "camera": "static", "density": "1", "image_quality": "good"}),
    "framing_bare_head": dict(
        intervals=ppe_mon(9.0, "worker behind timber framing"),
        events=[E("framing_bare_head-E01", PPE, "violation", 0.0, 9.0, 0.0, 0.0, "worker in light-blue shirt", "partial",
                  "assumed", frames=(0, 120, 192),
                  note="Bare head seen from behind and the side, partly occluded by studs; nobody in view wears a hard hat."),
                E("framing_bare_head-E02", PPE, "uncertain", 0.0, 9.0, 0.0, 0.0, "second person, dark clothing, background right",
                  "low", note="Dim; headwear not identifiable.")],
        people={"distinct_workers": 2, "basis": "static view"},
        attributes={"lighting": "indoor, dim", "distance": "near", "camera": "static", "density": "2",
                    "image_quality": "good, shallow focus"}),
    "c00": dict(
        intervals=[I(PPE, 0.0, 59.0, "unobservable", "distant site views and a suspended panel lift; workers tiny"),
                   I(PPE, 59.0, 137.0, "monitorable", "mid and close shots; all identifiable heads wear white hard hats"),
                   I(PPE, 137.0, 203.0, "unobservable", "distant views through trees; workers tiny"),
                   I(PPE, 203.0, 255.0, "monitorable", "mid and close shots; white hard hats"),
                   I(PPE, 255.0, 392.59, "monitorable", "crane close-ups and stadium views; no people visible")],
        events=[],
        people={"distinct_workers": None, "basis": "hand-held telephoto with zooms and cuts: not countable"},
        attributes={"lighting": "day", "distance": "mixed, mostly far", "camera": "hand-held telephoto, zooms and cuts",
                    "density": "0-4", "image_quality": "good"}),
    "c01": dict(
        intervals=[I(PPE, 0.0, 22.0, "unobservable", "distant view of the pour"),
                   I(PPE, 22.0, 40.0, "uncertain", "mid shot; heads small; the pink-suited worker's dark headwear is not "
                                                   "reliably identifiable at this size"),
                   I(PPE, 40.0, 69.6, "monitorable", "close shot of the pour crew"),
                   I(PPE, 69.6, 71.0, "unusable", "cross-dissolve"),
                   I(PPE, 71.0, 90.7, "unobservable", "distant view"),
                   I(PPE, 90.7, 115.0, "monitorable", "mid shot; two workers in white hard hats"),
                   I(PPE, 115.0, 127.0, "unobservable", "townscape; tiny figures"),
                   I(PPE, 127.0, 140.0, "uncertain", "mid-distance; heads small"),
                   I(PPE, 140.0, 148.0, "unusable", "cross-dissolve"),
                   I(PPE, 148.0, 176.0, "unobservable", "distant"),
                   I(PPE, 176.0, 199.5, "uncertain", "distant-mid through foliage; heads small"),
                   I(PPE, 199.5, 229.9, "monitorable", "close shot of the pour crew"),
                   I(PPE, 229.9, 230.5, "unusable", "cut"),
                   I(PPE, 230.5, 245.0, "uncertain", "worker in dark rigid headwear: hard hat or not unclear"),
                   I(PPE, 245.0, 272.0, "monitorable", "close shot; white hard hats"),
                   I(PPE, 272.0, 310.0, "unobservable", "distant site views"),
                   I(PPE, 310.0, 334.0, "monitorable", "street with a lorry, then foliage; no workers visible"),
                   I(PPE, 334.0, 362.06, "uncertain", "mid-distance worker in orange; head small")],
        events=[E("c01-E01", PPE, "violation", 41.0, 58.0, 1.0, 2.0, "pink-suited worker, navy soft cap", "partial", "evident",
                  frames=(1229, 1648), note="Co-workers in the same shot wear white hard hats; head sometimes cut by the frame top."),
                E("c01-E02", PPE, "violation", 50.0, 69.5, 1.5, 0.5, "white-suited worker, dark hood or balaclava", "partial",
                  "evident", frames=(1543, 1858)),
                E("c01-E03", PPE, "violation", 200.5, 229.9, 1.0, 0.5, "pink-suited worker, navy soft cap", "partial", "evident",
                  frames=(6024, 6474, 6773)),
                E("c01-E04", PPE, "violation", 200.5, 229.9, 1.0, 0.5, "white-suited worker, dark hood or balaclava",
                  "partial", "evident", frames=(6174, 6548, 6848))],
        people={"distinct_workers": None, "basis": "many shots and cuts: not countable"},
        attributes={"lighting": "day", "distance": "mixed", "camera": "hand-held telephoto, cuts and cross-dissolves",
                    "density": "1-6", "image_quality": "good"}),
    "c02": dict(
        intervals=[I(PPE, 0.0, 50.0, "monitorable", "workers in white hard hats, then building details with no people"),
                   I(PPE, 50.0, 106.0, "uncertain", "telehandler; operator in the cab and partly hidden workers"),
                   I(PPE, 106.0, 183.0, "monitorable", "concrete skip on the crane; no people visible"),
                   I(PPE, 183.0, 195.0, "unusable", "cross-dissolve"),
                   I(PPE, 195.0, 216.0, "uncertain", "upper-right worker's headwear unclear"),
                   I(PPE, 216.0, 239.0, "monitorable", "suspended pallets; no people"),
                   I(PPE, 239.0, 333.33, "monitorable", "crew through foliage; all identifiable heads wear white hard hats")],
        events=[],
        people={"distinct_workers": None, "basis": "hand-held, cuts: not countable"},
        attributes={"lighting": "day, overcast", "distance": "mid", "camera": "hand-held telephoto, cuts",
                    "density": "0-6", "image_quality": "good"}),
    "c03": dict(
        intervals=[I(PPE, 0.0, 24.5, "monitorable", "one scaffolder in a yellow hard hat and harness"),
                   I(PPE, 24.5, 27.5, "unobservable", "wide shot; the worker is tiny"),
                   I(PPE, 27.5, 33.04, "monitorable", "city view; no people")],
        events=[],
        people={"distinct_workers": 1, "basis": "single worker"},
        attributes={"lighting": "day", "distance": "near to far", "camera": "hand-held, pans at the end", "density": "1",
                    "image_quality": "good"}),
    "c07": dict(
        intervals=[I(PPE, 0.0, 3.0, "unusable", "black, fade-in"),
                   I(PPE, 3.0, 17.0, "monitorable", "title cards; no people"),
                   I(PPE, 17.0, 35.0, "not_applicable", "studio interview: no head-protection requirement"),
                   I(PPE, 35.0, 41.0, "uncertain", "outdoor mast-climber shot; any person is tiny"),
                   I(PPE, 41.0, 64.5, "not_applicable", "studio interview"),
                   I(PPE, 64.5, 68.0, "uncertain", "outdoor shot; small figure on the mast"),
                   I(PPE, 68.0, 75.0, "not_applicable", "studio interview"),
                   I(PPE, 75.0, 88.82, "monitorable", "credits; no people")],
        events=[],
        people={"distinct_workers": 1, "basis": "one interviewee"},
        attributes={"lighting": "studio", "distance": "near", "camera": "edited video", "density": "1",
                    "image_quality": "good"}),
    "c08": dict(
        intervals=[I(PPE, 0.0, 1.5, "unusable", "fade-in"),
                   I(PPE, 1.5, 11.0, "monitorable", "street works beside a mini excavator"),
                   I(PPE, 11.0, 13.12, "unusable", "fade-out")],
        events=[E("c08-E01", PPE, "violation", 1.5, 11.0, 0.5, 0.5, "worker in dark clothes beside the excavator", "partial",
                  "assumed", frames=(50, 200), note="Bare head; nobody on this site wears a hard hat."),
                E("c08-E02", PPE, "violation", 1.5, 11.0, 0.5, 0.5, "worker in green beside the excavator", "partial", "assumed",
                  frames=(50, 200)),
                E("c08-E03", PPE, "uncertain", 1.5, 11.0, 0.5, 0.5, "excavator operator in the cab", "low"),
                E("c08-E04", PPE, "not_applicable", 1.5, 11.0, 0.5, 0.5, "pedestrians in the background street", "low",
                  note="Members of the public.")],
        people={"distinct_workers": "4-5", "basis": "two workers, the operator, passing pedestrians"},
        attributes={"lighting": "day", "distance": "mid", "camera": "static", "density": "3-5", "image_quality": "good"}),
    "c09": dict(
        intervals=[I(PPE, 0.0, 13.0, "uncertain", "rooftop crew; heads under about 12 px; no hard hat visible on anyone")],
        events=[E("c09-E01", PPE, "violation", 0.0, 13.0, 0.0, 0.0, "rooftop crew (group of 5-7)", "low", "assumed",
                  frames=(0, 345), note="Group episode: individual workers not separable at this resolution.")],
        people={"distinct_workers": "5-7", "basis": "rooftop crew"},
        attributes={"lighting": "day", "distance": "far", "camera": "hand-held, zoom", "density": "5-7",
                    "image_quality": "low (640x480)"}),
    "c10": dict(
        intervals=[I(PPE, 0.0, 14.5, "uncertain", "distant roof crew"),
                   I(PPE, 14.5, 27.5, "monitorable", "lorry, mixer and sky; no people visible"),
                   I(PPE, 27.5, 43.5, "uncertain", "zoomed roof crew; heads about 8-10 px"),
                   I(PPE, 43.5, 55.0, "uncertain", "lorry area; possible small figure"),
                   I(PPE, 55.0, 91.97, "uncertain", "roof crew at mid and far distance")],
        events=[E("c10-E01", PPE, "violation", 0.0, 14.5, 0.0, 1.0, "rooftop crew (group of 5-7)", "low", "assumed"),
                E("c10-E02", PPE, "violation", 27.5, 43.5, 1.0, 1.0, "rooftop crew (group of 5-7)", "low", "assumed",
                  frames=(870, 930)),
                E("c10-E03", PPE, "violation", 55.0, 91.97, 1.5, 0.0, "rooftop crew (group of 5-7)", "low", "assumed")],
        people={"distinct_workers": "5-7", "basis": "same crew as c09"},
        attributes={"lighting": "day", "distance": "far", "camera": "hand-held, zooms and cuts", "density": "5-7",
                    "image_quality": "low (640x480)"}),
    "c11": dict(
        intervals=[I(PPE, 0.0, 6.0, "unusable", "black, then a blurred pan"),
                   I(PPE, 6.0, 13.0, "uncertain", "forklift with a small driver"),
                   I(PPE, 13.0, 16.0, "monitorable", "hands and a model forklift; no heads"),
                   I(PPE, 16.0, 30.0, "not_applicable", "office and classroom scenes"),
                   I(PPE, 30.0, 31.5, "monitorable", "wheel and shoes; no heads"),
                   I(PPE, 31.5, 38.0, "uncertain", "instructors or visitors without hard hats beside a forklift, one holding "
                                                   "a hard hat; requirement for them unknown"),
                   I(PPE, 38.0, 39.0, "monitorable", "close-up of a white hard hat"),
                   I(PPE, 39.0, 50.0, "uncertain", "bare-headed reach-truck driver (requirement unknown) and a walker in a "
                                                   "hard hat"),
                   I(PPE, 50.0, 59.0, "uncertain", "overhead view of aisles; people small"),
                   I(PPE, 59.0, 69.0, "uncertain", "bare-headed instructor with megaphone; requirement unknown"),
                   I(PPE, 69.0, 75.0, "monitorable", "trainee in a white hard hat; structure close-up"),
                   I(PPE, 75.0, 78.5, "uncertain", "bare-headed instructor with megaphone"),
                   I(PPE, 78.5, 88.0, "monitorable", "trainees in numbered hard hats"),
                   I(PPE, 88.0, 90.0, "unusable", "dark frames"),
                   I(PPE, 90.0, 94.0, "monitorable", "trainee in a numbered hard hat"),
                   I(PPE, 94.0, 103.16, "monitorable", "fork close-ups; no heads")],
        events=[],
        people={"distinct_workers": None, "basis": "edited film: not countable"},
        attributes={"lighting": "indoor, black and white", "distance": "mixed", "camera": "edited film",
                    "density": "1-6", "image_quality": "archival (720x576)"}),
    "c12": dict(
        intervals=ppe_mon(69.8, "concrete saw close-up; no people; compression artefacts around 36.8 s and 50.6 s"),
        events=[],
        people={"distinct_workers": 0, "basis": "no people"},
        attributes={"lighting": "day, overcast", "distance": "near", "camera": "static", "density": "0", "image_quality": "good"}),
}


def main():
    with open(ROOT / "reports" / "validation" / "clip_manifest.csv", encoding="utf-8") as f:
        man = {r["clip_id"]: r for r in csv.DictReader(f) if r["evaluated"] == "yes"}
    zones = json.loads((ROOT / "models" / "runtime_config.json").read_text())["zones"]
    OUT.mkdir(parents=True, exist_ok=True)
    for cid, c in CLIPS.items():
        r = man[cid]
        blind, why = BLIND[r["split"]]
        lab = {"schema": SCHEMA, "label_set": SET, "clip_id": cid, "file": r["file"], "sha256": r["sha256"], "fps": float(r["fps"]),
               "frames": int(r["frames_decoded"]), "duration_s": float(r["duration_s"]), "split": r["split"],
               "source_group": r["source_group"], "status": "provisional",
               "annotators": [{"id": ANNOTATOR, "kind": "ai", "role": "first-pass", "date": "2026-11-05",
                               "blind_to_model_output": blind, "notes": why + " Labelled from contact sheets (about 30 frames per "
                               "clip) and detail crops; boundaries carry the stated uncertainty."}],
               "reviews": [],
               "scope": {PPE: "evaluated", ZONE: "evaluated" if cid in zones else NO_ZONE},
               "zones": [{**z, "kind": z.get("kind", "restricted"), "real_restriction": False,
                          "basis": "drawn for the demo; the people inside are doing their normal work there",
                          "authorization": "unknown"} for z in zones.get(cid, [])],
               "intervals": c["intervals"], "events": c["events"], "people": c["people"], "attributes": c["attributes"]}
        validate(lab)
        (OUT / f"{cid}.json").write_text(json.dumps(lab, indent=1), encoding="utf-8")
        print(cid, len(c["events"]), "events", len(c["intervals"]), "intervals")


if __name__ == "__main__":
    main()
