import os
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
AUDIO_DIR = ROOT_DIR / "audio_out"
TMP_DIR = ROOT_DIR / "tmp"

for d in (DATA_DIR, REPORTS_DIR, AUDIO_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    result = "".join('_' if c in bad else c for c in name)
    return result.strip().replace(" ", "_")


def ensure_ext(path: str, ext: str) -> str:
    p = Path(path)
    if p.suffix.lower() != ext.lower():
        return str(p.with_suffix(ext))
    return str(p)
