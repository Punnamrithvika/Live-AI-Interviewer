from __future__ import annotations

from pathlib import Path
from typing import Optional

# Lazy-import heavy/optional deps so --no-audio runs without them installed
try:
    from playsound import playsound  # type: ignore
except Exception:  # pragma: no cover
    playsound = None  # type: ignore

from ..utils.file_utils import AUDIO_DIR, ensure_ext, timestamp


def text_to_speech(text: str, filename: Optional[str] = None, play: bool = True) -> str:
    """Convert text to speech using gTTS and optionally play it.

    Returns the mp3 file path.
    """
    if not filename:
        filename = f"tts_{timestamp()}.mp3"
    filename = ensure_ext(filename, ".mp3")
    out_path = Path(AUDIO_DIR) / filename

    # Import gTTS only when needed; if unavailable, skip audio generation gracefully
    try:
        from gtts import gTTS  # type: ignore
    except Exception:
        # Dependency not installed: return empty path but keep app running (useful for --no-audio)
        return ""

    tts = gTTS(text)
    tts.save(str(out_path))

    if play and playsound is not None:
        try:
            playsound(str(out_path))
        except Exception:
            # Swallow playback errors; file is saved regardless
            pass

    return str(out_path)
