from __future__ import annotations

from typing import Dict, List
import random

from ..utils.cohere_client import generate_text
from ..audio.text_to_speech import text_to_speech
from ..audio.speech_to_text import SpeechToText
from ..utils.storage import SessionStore
try:
    from ..scoring.trained_model import score_candidate_answer_with_feedback as score_with_feedback  # type: ignore
    _HAS_WITH_FEEDBACK = True
except Exception:
    from ..scoring.trained_model import score_candidate_answer_realtime as score_answer  # type: ignore
    _HAS_WITH_FEEDBACK = False

LEVEL_PROMPTS: Dict[str, str] = {
    "basic": (
        "Ask a simple, concept-based question that checks the candidate's understanding of the core principles in this skill."
        "Ensure the question is clear, direct, and helps assess grasp of the basics rather than complex application."

    ),
    "intermediate": (
        "Ask a moderately challenging question that requires the candidate to apply concepts or explain reasoning with an example."
        "The question should connect related ideas and test both understanding and practical thinking."
    ),
    "advanced": (
        "Ask a challenging, real-world question that tests the candidate's ability to analyze scenarios, design efficient solutions,"
        "and reason about trade-offs. The question should encourage problem-solving and decision-making at an advanced level."
    ),
}



def _make_skill_prompt(skill: str, level: str, prev_responses: List[str]) -> str:
    ctx = "\n".join(prev_responses[-2:]) if prev_responses else ""
    # Short prompt: include skill, level, level-specific guidance, and last two responses if any
    prompt = (
        f"Skill: {skill}\n"
        f"Level: {level}\n"
        f"Guidance: {LEVEL_PROMPTS[level]}\n"
    )
    if ctx:
        prompt += f"Last 2 responses:\n{ctx}\n"
    prompt += (
        "Generate 1 concise question.\n"
        "Do not repeat or paraphrase the same topic as earlier questions; vary the subtopic within the skill."
    )
    return prompt


# ---- Similarity and distinct generation helpers (moved from server) ----
import re
from typing import List as _List


def normalize_question(text: str) -> str:
    s = (text or "").strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\?{2,}", "?", s)
    s = re.sub(r"\?+$", "?", s) if s else s
    if s and not s.endswith('?') and len(s) > 8:
        s += '?'
    return s


def _token_set(text: str) -> set:
    t = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    toks = [w for w in t.split() if len(w) > 2]
    return set(toks)

# Lightweight stopword list to reduce trivial overlaps
_STOP = {
    'the','and','for','with','that','this','from','into','your','about','have','would','could','should','what','when','why','how',
    'you','are','was','were','will','can','did','does','is','it','its','their','them','they','each','such','than','then','else',
    'use','case','real','world','give','explain','define','tell','me','design','decision','under','high','load','one','two','more',
    'example','examples','system','systems','service','services','data','based','using','used'
}

def _keywords(text: str, limit: int = 6) -> _List[str]:
    toks = [t for t in _token_set(text) if t not in _STOP]
    # sort by length desc as a proxy for specificity
    toks.sort(key=len, reverse=True)
    return toks[:limit]

def _recent_topics(store: SessionStore, n: int = 3) -> _List[str]:
    qs = _recent_skill_questions(store, n=n)
    seen: dict[str, int] = {}
    for q in qs:
        for k in _keywords(q):
            seen[k] = seen.get(k, 0) + 1
    # return top keywords by frequency then length
    return [k for k, _ in sorted(seen.items(), key=lambda kv: (-kv[1], -len(kv[0])))]


def _similarity(a: str, b: str) -> float:
    A = _token_set(a)
    B = _token_set(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    denom = max(len(A), len(B))
    return inter / denom if denom else 0.0


def _recent_skill_questions(store: SessionStore, n: int = 8) -> _List[str]:
    items = (store.state.get("phases", {}) or {}).get("skills", []) or []
    return [ (it or {}).get("question") or "" for it in items[-n:] ]


def _pick_distinct_question_from_raw(raw: str, recent: _List[str], threshold: float = 0.5) -> str:
    lines = []
    analysis_prefixes = ("the candidate", "candidate ", "strength", "weakness", "overall")
    for line in (raw or "").splitlines():
        original = line
        line = line.strip("-• ").strip()
        if not line:
            continue
        low = line.lower()
        if any(low.startswith(p) for p in analysis_prefixes):
            continue
        if '?' not in line:
            continue
        lines.append(normalize_question(line))
    for cand in lines:
        if all(_similarity(cand, prev) < threshold for prev in recent if prev):
            return cand
    raise ValueError("No distinct question found below similarity threshold")


def generate_distinct_skill_question(skill: str, level: str, store: SessionStore, max_attempts: int = 3) -> str:
    """Retry LLM with explicit avoidance of recent questions and return a distinct question.

    Instrumented with debug logging via print statements (can be replaced by logger) to diagnose failures.
    Raises ValueError if unable to produce a distinct question after retries.
    """
    recent_qs = _recent_skill_questions(store, n=8)
    recent_topics = _recent_topics(store, n=4)
    prev_resps = store.get_last_responses("skills", 2)
    base_prompt = _make_skill_prompt(skill, level, prev_resps)
    avoid_block = "\n".join(f"- {q}" for q in recent_qs if q)

    attempt = 0
    last_error: str | None = None
    while attempt < max_attempts:
        attempt += 1
        prompt = (
            f"{base_prompt}\n"
            "Avoid repeating or paraphrasing any of these prior questions:\n"
            f"{avoid_block}\n"
            "Constraints:\n"
            "- The question must be different by both wording and focus.\n"
            "- Do not reuse the same phrases or ask the same topic in different words.\n"
            f"- Avoid these topics/keywords seen recently: {', '.join(recent_topics) if recent_topics else 'none'}.\n"
            "- Output exactly one line question.\n"
        )
        raw = None
        try:
            raw = generate_text(prompt)
            if not raw:
                print(f"[skills_gen] attempt={attempt} empty raw response")
        except Exception as e:  # capture underlying exception detail
            last_error = str(e)
            print(f"[skills_gen] attempt={attempt} generate_text error: {e}")
            raw = None
        if raw:
            try:
                cand = _pick_distinct_question_from_raw(raw or "", recent_qs, threshold=0.4)
                print(f"[skills_gen] attempt={attempt} picked distinct question: {cand}")
                return cand
            except Exception as e:
                last_error = f"distinct-pick failed: {e}"
                print(f"[skills_gen] attempt={attempt} parsing/similarity rejection: {e}; raw={raw!r}")
    raise ValueError(f"Failed to generate distinct skill question after {max_attempts} attempts; last_error={last_error}")


import random
from ..utils.cohere_client import generate_text
from ..utils.storage import SessionStore

def get_next_skill_question(
    skill: str,
    level: str,
    store: SessionStore,
    use_analysis_prob: float = 0.7,
    max_attempts: int = 2
) -> str:
    """
    Hybrid Adaptive Question Generator

    Strategy:
    - 70% (adaptive mode): Analyze candidate's last response to probe weaknesses or raise complexity.
    - 30% (diversity mode): Ask a fresh question from a new subtopic within the same skill.
    - Always ensures distinctness vs. recent questions and topics.

    Args:
        skill: Target skill domain (e.g., 'OOPs', 'DBMS').
        level: Difficulty level ('beginner' | 'intermediate' | 'advanced').
        store: Shared session store containing past questions/answers.
        use_analysis_prob: Probability (0–1) of using adaptive mode.
        max_attempts: Retry count for question generation fallback.

    Returns:
        str: A single distinct, concise interview question.
    """

    recent_qs = _recent_skill_questions(store, n=8)
    recent_topics = _recent_topics(store, n=4)
    phases = store.state.get("phases", {})
    skills_hist = phases.get("skills", []) if isinstance(phases.get("skills"), list) else []
    last = skills_hist[-1] if skills_hist else {}
    last_q = (last or {}).get("question", "")
    last_a = (last or {}).get("answer", "")

    # Decide mode (adaptive vs fresh)
    use_analysis = (random.random() < use_analysis_prob) and bool(last_q and last_a)

    for attempt in range(1, max_attempts + 1):
        if use_analysis:
            # Adaptive mode: analyze response + generate question
            prompt = f"""
            You are a technical interviewer for the skill "{skill}" at {level} level.

            Candidate's previous exchange:
            Question: {last_q}
            Answer: {last_a}

            Step 1: Briefly assess the candidate's understanding in one line.
            Step 2: Based on that, generate ONE next interview question that either:
            - Probes weak or uncertain areas, OR
            - Advances to a slightly more challenging concept within "{skill}".
            
            Constraints:
            - Do NOT repeat or paraphrase the previous question or answer.
            - Avoid these recent topics: {', '.join(recent_topics) if recent_topics else 'none'}.
            - Keep it short (max ~20 words) and natural interview-style.
            - Output ONLY the next question (no numbering, no explanation).
            """
        else:
            # Diversity mode: fresh subtopic question
            prompt = f"""
            Generate ONE new interview question for the skill "{skill}" at {level} level.

            Constraints:
            - Avoid repeating or paraphrasing previous questions.
            - Cover a different subtopic than recent ones (avoid: {', '.join(recent_topics) if recent_topics else 'none'}).
            - Keep it concise (max ~20 words), realistic interview-style.
            - Output ONLY the question, no prefix or numbering.
            """

        try:
            raw = generate_text(prompt)
        except Exception as e:
            print(f"[skills_adapt] attempt={attempt} generate_text error: {e}")
            continue

        if not raw:
            continue

        try:
            cand = _pick_distinct_question_from_raw(raw, recent_qs, threshold=0.4)
            print(f"[skills_adapt] attempt={attempt} mode={'adaptive' if use_analysis else 'fresh'} -> {cand}")
            return cand
        except Exception as e:
            print(f"[skills_adapt] attempt={attempt} rejection: {e}; raw={raw!r}")
            continue

    # Fallback — force distinct new question if all attempts fail
    return generate_distinct_skill_question(skill, level, store, max_attempts=3)


def run_skills_interaction(store: SessionStore, skills: List[str], play_audio: bool = True) -> None:
    stt = SpeechToText()

    for skill in skills:
        level_order = ["basic", "intermediate", "advanced"]
        current_index = 0
        level_results: Dict[str, Dict] = {}

        while current_index < len(level_order):
            level = level_order[current_index]
            passes = 0
            fails = 0
            asked = 0

            # Ask up to 3 single questions for this level; stop early on 2 passes or 2 fails
            for _ in range(3):
                # Adaptive/fresh selection with distinctness enforcement
                try:
                    q = get_next_skill_question(skill, level, store, use_analysis_prob=0.7, max_attempts=2)
                except Exception:
                    try:
                        q = generate_distinct_skill_question(skill, level, store, max_attempts=3)
                    except Exception:
                        # Minimal fallback per level
                        if level == "basic":
                            q = f"Define {skill} in one sentence?"
                        elif level == "intermediate":
                            q = f"Give a real-world use case for {skill} and key trade-offs?"
                        else:
                            q = f"Design decision: how would you scale {skill} under high load?"

                text_to_speech(q, play=play_audio)
                answer = stt.listen(timeout=8.0, phrase_time_limit=90.0)
                if _HAS_WITH_FEEDBACK:
                    score, fb = score_with_feedback(q, answer, level)
                    store.add_qa("skills", q, answer, score, fb)
                else:
                    score = score_answer(q, answer, level)
                    store.add_qa("skills", q, answer, score)
                asked += 1
                if score >= 30:
                    passes += 1
                else:
                    fails += 1

                if passes >= 2 or fails >= 2:
                    break

            # Decide progression for this level
            passed_level = passes >= 2
            # Concise per-level feedback
            if passed_level:
                level_fb = f"Passed {passes}/{asked} at {level}."
            else:
                level_fb = f"Below threshold with {fails}/{asked} incorrect at {level}."

            level_results[level] = {"passes": passes, "fails": fails, "asked": asked, "passed_level": passed_level, "feedback": level_fb}
            store.add_skill_result(skill, level, passed_level, level_results[level])

            if not passed_level and fails >= 2:
                # Mark not proficient and stop progressing for this skill
                break
            else:
                current_index += 1
