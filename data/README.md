# Data

Only two manifests are tracked here:

| File | Purpose |
|---|---|
| `demo/demo_clips.json` | The five demo clips: file name, title, frame count, fps, source page, licence, author |
| `demo/candidates.json` | Licence metadata for the Wikimedia Commons clips that were reviewed (including the unseen-footage set) |

Everything else in `data/` is generated locally and git-ignored:
- `raw/`: original dataset downloads
- `processed/`: leak-free training sets
- `demo/*.mp4`: demo clips
- `demo/uploads/`: videos uploaded in the app
- `cache/`: gallery thumbnails

## Demo footage

The app lists the clips in `demo/demo_clips.json` that exist on disk. To recreate them:

```powershell
python training\fetch_demo_candidates.py   # Wikimedia Commons clips (CC BY-SA) into data\demo\candidates
python training\fetch_mixkit.py            # Mixkit clips into data\demo\mixkit (licence: Mixkit Stock Video Free License)
python training\prepare_demo.py            # transcode the reviewed clips to 1280-wide MP4 in data\demo
```

These need internet access. The Mixkit clips are fetched rather than shipped, because their standalone redistribution is unconfirmed. Without any clips, you can still use **Upload video** or **Webcam** in the app.

| Clip | Source | Licence |
|---|---|---|
| track_work_day | Wikimedia Commons, MHM55 | CC BY-SA 4.0 |
| roadworks_night | Wikimedia Commons, Nesnad | CC BY-SA 3.0 |
| ballast_train | Wikimedia Commons, Stevenlodz | CC BY-SA 4.0 |
| helmet_put_on | Mixkit clip 1440 | Mixkit free licence (not redistributed) |
| framing_bare_head | Mixkit clip 1459 | Mixkit free licence (not redistributed) |

## Training data

Retraining needs the datasets in [docs/datasets_and_licensing.md](../docs/datasets_and_licensing.md), downloaded into `data/raw/` and prepared with the scripts in `training/`; see [docs/training.md](../docs/training.md). The datasets are not redistributed here, and SH17 alone is about 14 GB.
