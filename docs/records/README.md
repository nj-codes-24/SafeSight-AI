# Project records

These files are **historical snapshots** written while the project was being built. They are kept unchanged, so file paths inside them refer to the layout of the time. For example, `DATASETS.md`, `PROJECT_STATUS.md` and the demo guides lived at the repository root, and some evaluation scripts lived in `tests/`. Current documentation is in [`docs/`](../).

| File | What it is |
|---|---|
| `PROJECT_STATUS.md` | Status at the model freeze: components, evidence, acceptance checks |
| `DATASETS.md` | Working record of datasets, cleaning and contribution per experiment |
| `DEMO_READINESS.md` | Demonstration-readiness audit (browser-tested), including performance measurements |
| `DEMO_GUIDE.md`, `DEMO_OPERATOR_GUIDE.md` | Demo guides written for the earlier dashboard and for the current interface |
| `FREEZE_MANIFEST.txt` | SHA-256 of the frozen files at the model freeze, using the paths of that time |

**Changes since the freeze manifest:**
- Files were moved into `docs/` and `scripts/`.
- The UI was redesigned.
- Two report JSON files had absolute local paths removed. Their numbers are unchanged, and the old and new hashes are in [REPOSITORY_AUDIT.md](../../REPOSITORY_AUDIT.md).
- `models/best.pt` is unchanged.
