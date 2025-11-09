from __future__ import annotations

from typing import Optional
import time

from ..audio.text_to_speech import text_to_speech
from ..audio.speech_to_text import SpeechToText
from ..utils.storage import SessionStore
from ..scoring.evaluate_intro import evaluate_intro_answer

def generate_intro_question(candidate_name: Optional[str] = None) -> str:
    """Return a fixed, concise intro question without calling an LLM.

    If a candidate name is provided, greet them by name.
    """
    name_part = f"Hi {candidate_name}! " if candidate_name else "Hi! "
    q = (
        name_part
        + "Can you briefly introduce yourself and highlight your background, strengths, and key experiences that make you a good fit for this role?"
    )
    # Ensure exactly one trailing question mark
    if not q.endswith("?"):
        q += "?"
    else:
        # collapse any duplicates at the end
        import re
        q = re.sub(r"\?+$", "?", q)
    return q

def run_intro_interaction(store: SessionStore, play_audio: bool = True) -> None:
    cname = (store.state.get("candidate") or {}).get("name") if hasattr(store, "state") else None
    question = generate_intro_question(cname)
    text_to_speech(question, play=play_audio)
    # Removed backend sleep; frontend manages thinking countdown

    stt = SpeechToText()
    answer = stt.listen(timeout=8.0, phrase_time_limit=60.0)

    score, feedback = evaluate_intro_answer(answer)
    store.add_qa("introduction", question, answer, score, feedback)
