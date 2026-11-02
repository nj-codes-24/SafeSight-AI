# Contributing

Thank you for your interest. SafeSight AI is an open-source academic research prototype, and issues and pull requests are welcome.

**Licence of contributions.** The project's code is licensed under [AGPL-3.0-only](LICENSE). By submitting a contribution, you agree that it is licensed under the same terms (inbound = outbound), and you confirm that you have the right to submit it. Do not contribute third-party code, data or media with incompatible terms. In particular, never add model weights, SH17-derived labels or images, or dataset files ([LICENSING_DECISION.md](LICENSING_DECISION.md)).

## Development setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python scripts\verify_installation.py
```

## Before opening a pull request

```powershell
ruff check .
python -m pytest -rs
```

- **CI** runs Ruff and the CPU-compatible tests on Windows. Integration tests in `tests/test_pipeline.py` need the M5 weights and data; run them locally if your change touches `inference/`, and say so in the pull request.
- **Keep changes focused,** and follow the style of the surrounding code.
- **Detection behaviour is frozen.** Changes to `inference/` that could alter detections, thresholds or incident decisions need evidence: before-and-after numbers on the same data, using the scripts in `training/` and `scripts/evaluation/`.
- **Never commit** weights, datasets, video, incident databases, evidence frames or credentials. `.gitignore` covers these; check `git status` before you commit.
- **Use Conventional Commit messages,** for example `feat(app): …`, `fix(inference): …`, `docs: …`.

## Reporting issues

Use the issue templates. For security problems, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
