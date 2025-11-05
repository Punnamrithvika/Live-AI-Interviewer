from __future__ import annotations
from typing import List, Dict
import time
import random

from ..utils.cohere_client import generate_text
from ..audio.text_to_speech import text_to_speech
from ..audio.speech_to_text import SpeechToText
from ..utils.storage import SessionStore
from ..scoring.evaluate_project import evaluate_project_answer


def _sanitize_topic(text: str) -> str:
    """Remove bracketed placeholders and common noise tokens from topic seeds."""
    t = text or ""
    # Strip [...] segments
    out = []
    skip = 0
    for ch in t:
        if ch == '[':
            skip += 1
            continue
        if ch == ']' and skip:
            skip -= 1
            continue
        if skip == 0:
            out.append(ch)
    t = ''.join(out)
    # Remove obvious noise tokens
    noise = {"audio", "transcription", "unavailable", "received", "kb"}
    words = [w.strip(',.;:') for w in t.split()]
    words = [w for w in words if w.lower() not in noise and len(w) >= 3]
    # Drop generic leading tokens
    generic_starts = {"worked", "working", "work", "project", "projects", "recent"}
    while words and words[0].lower() in generic_starts:
        words.pop(0)
    t = " ".join(words)
    return t.strip()

def _normalize_question(q: str) -> str:
    import re
    q = (q or "").strip().strip('"').strip("'")
    # Collapse any run of ? into a single ?
    q = re.sub(r"\?{2,}", "?", q)
    q = q.replace('?"', '?').replace("?'", '?')
    if not q.endswith('?') and len(q) > 8:
        q += '?'
    return q


def generate_project_question_for_one(
    project: Dict[str, str],
    prev_responses: List[str],
) -> str:
    """
    Generate one project-based interview question using the LLM.
    If LLM fails, fallback to a deterministic question.
    """

    title_raw = (project.get("project_title") or "").strip()
    summary = (project.get("summary") or "No summary available").strip()

    # use module-level _sanitize_topic

    # Build a display title that is never generic
    def _derive_topic_from_summary(s: str, max_words: int = 6) -> str:
        s = _sanitize_topic(s or "")
        if not s:
            return "recent work"
        # Lightweight keyword derivation: take first few non-trivial words
        words = [w.strip(',.;:') for w in s.split() if len(w.strip(',.;:')) >= 3]
        return " ".join(words[:max_words]) or "recent work"

    is_generic = title_raw.lower() in {"", "project", "your project", "n/a", "na"}
    display_title = title_raw if not is_generic else f"{_derive_topic_from_summary(summary)}"

    prev_ctx = "\n".join(prev_responses[-2:]) if prev_responses else ""

    # 🎯 Clear, rewritten prompt for single project
    prompt = f"""
You are an AI interviewer. Generate ONE concise technical interview question
based on the candidate's project below. The question MUST explicitly reference the project title or topic.

Project title: {title_raw or '[unknown]'}
Summary: {summary}

Candidate’s recent responses (if any):
{prev_ctx or 'None'}

Guidelines:
- Focus ONLY on this project.
- Avoid repeating questions like “Tell me about this project”.
- Ask about real challenges, technical decisions, or measurable impact.
- Output only ONE clear question.
"""

    try:
        raw = generate_text(prompt).strip()
        # Pick the first valid question-like line
        for line in raw.splitlines():
            line = line.strip("-• ").strip()
            if line:
                if not line.endswith("?") and len(line) > 8:
                    line += "?"
                # Ensure the question explicitly mentions the true project title when available
                low = line.lower()
                if title_raw and title_raw.lower() in low:
                    return _normalize_question(line)
                # If LLM didn't mention the actual project, prefix context
                prefix = (
                    f"In {title_raw}, " if (title_raw and not is_generic) else f"Regarding your work on {display_title}, "
                )
                base = line.lstrip('\"\'')
                base = base[0].lower() + base[1:] if base and base[0].isupper() else base
                return _normalize_question(f"{prefix}{base}")
    except Exception:
        pass

    # 🧩 Fallback if LLM fails
    prefix = (
        f"In {title_raw}, " if (title_raw and not is_generic) else f"Regarding your work on {display_title}, "
    )
    fallback_bank = [
        f"{prefix}what was the most difficult technical issue you solved and how?",
        f"{prefix}what key design or architectural choice did you make and why?",
        f"{prefix}what measurable impact or improvement did you achieve?",
    ]
    return _normalize_question(random.choice(fallback_bank))


def generate_project_questions(projects: List[Dict[str, str]], prev_responses: List[str], total: int = 3) -> List[str]:
    """Generate up to `total` project-based questions.

    Uses the single-project generator per project to ensure questions reference the
    candidate's actual projects. If projects are unavailable, synthesize a topic from
    recent responses to keep questions specific rather than generic.
    """
    # If no projects are available (e.g., resume not parsed), synthesize a pseudo-project
    # topic from the latest responses so the question is still specific.
    if not projects:
        def _derive_topic_from_responses(resps: List[str]) -> str:
            text = _sanitize_topic(" ".join(resps or []))
            if not text:
                return "recent work"
            # Keep a few non-trivial tokens for context
            words = [w.strip(',.;:') for w in text.split() if len(w.strip(',.;:')) >= 3]
            return " ".join(words[:6]) or "recent work"

        synth = {"project_title": "", "summary": _derive_topic_from_responses(prev_responses)}
        qs: List[str] = []
        seen = set()
        i = 0
        while len(qs) < total and i < total * 3:
            q = generate_project_question_for_one(synth, prev_responses)
            if q not in seen:
                qs.append(q)
                seen.add(q)
            i += 1
        return qs

    qs: List[str] = []
    i = 0
    seen = set()
    while len(qs) < total and i < max(total * 2, len(projects) * 3):
        proj = projects[i % len(projects)]
        q = generate_project_question_for_one(proj, prev_responses)
        if q not in seen:
            qs.append(q)
            seen.add(q)
        i += 1
    # Safety: ensure we always return `total` items by regenerating (with iteration limit to prevent infinite loop)
    safety_counter = 0
    max_attempts = total * 5  # reasonable upper bound
    while len(qs) < total and safety_counter < max_attempts:
        safety_counter += 1
        proj = projects[len(qs) % len(projects)] if projects else {"project_title": "", "summary": "recent work"}
        q = generate_project_question_for_one(proj, prev_responses)
        if q not in set(qs):
            qs.append(q)
        else:
            # As a last resort, add a minimally varied version referencing the project/topic
            title = (proj.get("project_title") or "this project").strip() or "this project"
            qs.append(f"In {title}, what was the toughest challenge and how did you solve it?")
    return qs


def run_projects_interaction(store: SessionStore, play_audio: bool = True) -> None:
    """
    Randomly selects one unasked project and generates one LLM-based question for it.
    """
    projects = store.state.get("projects", [])
    prev_responses = store.get_last_responses("introduction", n=2)
    asked_projects = store.state.get("asked_projects", [])

    # 🎯 Pick one random project not yet asked
    unasked_projects = [p for p in projects if p.get("project_title") not in asked_projects]
    if not unasked_projects:
        unasked_projects = projects[:]  # reset once all are asked

    selected_project = random.choice(unasked_projects)
    question = generate_project_question_for_one(selected_project, prev_responses)

    stt = SpeechToText()

    # 🎤 Ask the question aloud
    text_to_speech(question, play=play_audio)
    time.sleep(5)
    answer = stt.listen(timeout=8.0, phrase_time_limit=90.0)

    # 🧮 Evaluate the answer
    score, feedback = evaluate_project_answer(answer)
    store.add_qa("projects", question, answer, score, feedback)

    # 📝 Mark this project as asked
    title = selected_project.get("project_title")
    if title and title not in asked_projects:
        asked_projects.append(title)
    store.state["asked_projects"] = asked_projects
