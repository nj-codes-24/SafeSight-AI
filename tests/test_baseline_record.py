"""Baseline verifier (scripts/validation/freeze_baseline.py): a protected document may only gain a marked note, and
removing that note must give back the original bytes exactly (milestone M3)."""
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freeze_baseline", ROOT / "scripts" / "validation" / "freeze_baseline.py")
fb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fb)

ORIGINAL = b"# Summary\n\n**Provisional.** Numbers below.\n| a | b |\n"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def test_a_marked_note_strips_back_to_the_original_bytes():
    noted = ORIGINAL.replace(b"# Summary\n", b"# Summary\n<!-- M3 note start -->\n\n> pointer\n<!-- M3 note end -->\n")
    assert noted != ORIGINAL and sha(fb.without_notes(noted)) == sha(ORIGINAL)


def test_any_other_edit_is_still_detected():
    noted = ORIGINAL.replace(b"# Summary\n", b"# Summary\n<!-- M3 note start -->\n> pointer\n<!-- M3 note end -->\n")
    tampered = noted.replace(b"Provisional", b"Validated")
    assert sha(fb.without_notes(tampered)) != sha(ORIGINAL)
    unterminated = ORIGINAL + b"<!-- M3 note start -->\nno end marker\n"
    assert fb.without_notes(unterminated) == unterminated  # an unclosed note is not stripped
