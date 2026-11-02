"""Download shortlisted Wikimedia Commons clips with licence metadata, and sample frames for review."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "data" / "demo" / "candidates"
UA = {"User-Agent": "SafeSightStudentProject/1.0"}
TITLES = [
    "Building construction Moira Close Broadwater Farm Haringey 2025 13.webm",
    "Building construction Moira Close Broadwater Farm Haringey 2025 16.webm",
    "Building construction Moira Close Broadwater Farm Haringey 2025 21.webm",
    "Worker dismantling scaffoldings.ogv",
    "Genève Cornavin travaux voie 4, 2023-23.webm",
    "Nowe tory na odcinku Łódź Fabr.- Widzew.webm",
    "Jackhammer-japan-july2013.ogv",
    "Mast Climber Stability Research.webm",
    "Walking down the Trubarjeva street.webm",
    "Nalijevanje betonske ploče.324.ogv",
    "Nalijevanje betonske ploče.325.ogv",
    "Opleiding vorheftruckchauffeur-33264.ogv",
    "2014-Concrete-saw.ogv",
]


def info(title):
    q = dict(action="query", format="json", titles=f"File:{title}", prop="imageinfo", iiprop="url|extmetadata",
             iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q), headers=UA)
    page = next(iter(json.load(urllib.request.urlopen(req, timeout=30))["query"]["pages"].values()))
    i = page["imageinfo"][0]
    m = i["extmetadata"]
    return {"title": title, "url": i["url"], "page": i["descriptionurl"], "license": m.get("LicenseShortName", {}).get("value"),
            "license_url": m.get("LicenseUrl", {}).get("value"), "artist": m.get("Artist", {}).get("value")}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for n, t in enumerate(TITLES):
        try:
            m = info(t)
            dst = OUT / f"c{n:02d}{Path(t).suffix}"
            if not dst.exists():
                req = urllib.request.Request(m["url"], headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
                    f.write(r.read())
                time.sleep(2)
            cap = cv2.VideoCapture(str(dst))
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            m.update(file=dst.name, fps=cap.get(cv2.CAP_PROP_FPS), frames=fc, w=int(cap.get(3)), h=int(cap.get(4)))
            tiles = []
            for fr in np.linspace(0, max(fc - 2, 1), 4).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(fr))
                ok, im = cap.read()
                if ok:
                    tiles.append(cv2.resize(im, (400, 225)))
            cap.release()
            if tiles:
                tiles += [np.zeros_like(tiles[0])] * (4 - len(tiles))
                strip = np.hstack(tiles)
                cv2.putText(strip, dst.name, (6, 24), 0, 0.7, (0, 255, 255), 2)
                m["strip"] = strip
            meta.append(m)
            print(dst.name, m["license"], m["frames"], m["fps"], m["w"], m["h"], flush=True)
        except Exception as e:
            print("FAILED", t, repr(e), flush=True)
    strips = [m.pop("strip") for m in meta if "strip" in m]
    cv2.imwrite(str(OUT.parent / "candidates_review.jpg"), np.vstack(strips), [cv2.IMWRITE_JPEG_QUALITY, 80])
    (OUT.parent / "candidates.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
