from __future__ import annotations

from typing import Dict, List

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
    prompt += "Generate 1 concise question."
    return prompt


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
                prompt = _make_skill_prompt(skill, level, store.get_last_responses("skills", 2))
                raw = generate_text(prompt)
                # Parse the first reasonable question line
                q: str = ""
                for line in (raw or "").splitlines():
                    line = line.strip("-• ")
                    if not line:
                        continue
                    if not line.endswith("?") and len(line) > 8:
                        line += "?"
                    q = line
                    break
                if not q:
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
