"""
Rule-based evaluation for the introduction answer.

Heuristic scoring (0–100):
- Technical skills mentioned (unique): up to 50 points
- Soft skills mentioned (unique): up to 20 points
- Experience signals (years, internships, projects): up to 20 points
- Length/structure bonus: up to 10 points

Notes:
- Purely lexical; no external dependencies. Safe default for empty inputs.
"""

from __future__ import annotations

import re
from typing import Iterable, Set, Tuple, List

# Common technical skills/technologies (phrases or single tokens)
TECH_SKILLS: tuple[str, ...] = (
    # Languages
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "kotlin", "scala",
    "c", "c++", "c#", "ruby", "php", "swift", "objective-c",
    # Web/Frameworks
    "react", "next.js", "nextjs", "node", "node.js", "express", "django", "flask", "fastapi",
    "spring", "spring boot", "graphql", "rest", "grpc",
    # Data/ML
    "sql", "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis", "kafka", "spark",
    "pandas", "numpy", "scikit-learn", "sklearn", "tensorflow", "pytorch",
    # DevOps/Cloud
    "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "github actions",
    "aws", "azure", "gcp", "google cloud", "cloud run", "cloud functions",
    # Misc
    "linux", "git", "ci/cd", "microservices", "api", "oop", "dsa",
)

# Soft skills/behaviors
SOFT_SKILLS: tuple[str, ...] = (
    "communication", "communicator", "leadership", "teamwork", "collaboration", "collaborative",
    "problem solving", "problem-solving", "analytical", "time management", "ownership", "accountability",
    "adaptability", "mentorship", "mentoring", "stakeholder", "presentation", "presenting",
)

# Experience indicators
EXPERIENCE_KEYWORDS: tuple[str, ...] = (
    "experience", "experienced", "intern", "internship", "project", "projects", "freelance",
    "research", "publication", "open source", "open-source", "startup", "industry",
)


def _norm(text: str) -> str:
    return (text or "").lower()


def _phrase_present(text: str, phrase: str) -> bool:
    """Case-insensitive word-boundary search; supports multi-word phrases."""
    # Handle special tokens that don't play well with \b (like c++/c#)
    specials = {
        "c++": r"(?<!\w)c\+\+(?!\w)",
        "c#": r"(?<!\w)c#(?!\w)",
        "next.js": r"\bnext\.?js\b",
        "node.js": r"\bnode\.?js\b",
        "ci/cd": r"\bci\s*/\s*cd\b",
        "scikit-learn": r"\bscikit-?learn\b",
        "open-source": r"\bopen-?source\b",
    }
    pattern = specials.get(phrase)
    if not pattern:
        escaped = re.escape(phrase)
        escaped = escaped.replace(r"\ ", r"\s+")  # allow any whitespace between words
        pattern = rf"\b{escaped}\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _count_unique(text: str, vocab: Iterable[str]) -> int:
    found: Set[str] = set()
    for ph in vocab:
        if _phrase_present(text, ph):
            found.add(ph)
    return len(found)


def _experience_score(text: str) -> int:
    score = 0
    # Years of experience (e.g., "3 years", "2.5 yrs", "5+ years")
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", text)
    if m:
        yrs = float(m.group(1))
        score += min(12, int(round(yrs * 2)))  # up to 12 points
    # Internships
    if _phrase_present(text, "intern") or _phrase_present(text, "internship"):
        score += 4
    # Projects (non-trivial mention)
    if _phrase_present(text, "project") or _phrase_present(text, "projects"):
        score += 4
    return min(score, 20)


def _length_bonus(text: str) -> int:
    n = len(text.strip())
    if n >= 150:
        return 10
    if n >= 100:
        return 8
    if n >= 60:
        return 6
    if n >= 30:
        return 4
    return 2


def evaluate_intro_answer(answer_text: str) -> Tuple[int, str]:
    text = _norm(answer_text)
    if not text.strip():
        return 0, "No answer captured."

    # Technical skills: up to TECH_SKILL_MAX unique x TECH_SKILL_WEIGHT
    tech_unique = _count_unique(text, TECH_SKILLS)
    tech_score = min(7, tech_unique) * 7

    # Soft skills: up to SOFT_SKILL_MAX unique x SOFT_SKILL_WEIGHT
    soft_unique = _count_unique(text, SOFT_SKILLS)
    soft_score = min(5, soft_unique) * 7

    # Experience signals: up to 20
    exp_score = _experience_score(text)

    # Length bonus: up to 10
    len_bonus = _length_bonus(text)

    total = tech_score + soft_score + exp_score + len_bonus
    # If the intro is extremely short, dampen the score
    if len(text.split()) < 8:
        total = min(total, 25)

    final_score = max(0, min(100, int(total)))

    # Build concise feedback based on what was detected/missing
    found_tech: List[str] = [ph for ph in TECH_SKILLS if _phrase_present(text, ph)]
    found_soft: List[str] = [ph for ph in SOFT_SKILLS if _phrase_present(text, ph)]

    years_hint = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", text)
    has_projects = _phrase_present(text, "project") or _phrase_present(text, "projects")

    positives: List[str] = []
    if found_tech:
        positives.append(f"mentioned tech: {', '.join(found_tech[:5])}{'…' if len(found_tech)>5 else ''}")
    if found_soft:
        positives.append(f"soft skills: {', '.join(found_soft[:3])}{'…' if len(found_soft)>3 else ''}")
    if years_hint:
        positives.append("stated years of experience")
    if has_projects:
        positives.append("referenced projects/work")

    lacks: List[str] = []
    if not years_hint:
        lacks.append("stated years of experience")
    if len(found_tech) < 3:
        lacks.append("specific technologies/frameworks (name 2–3)")
    if not has_projects:
        lacks.append("mention of 1–2 key projects or responsibilities")
    # Simple impact signal
    if not any(x in text for x in ["%", "impact", "improved", "reduced", "increased", "users", "latency", "throughput"]):
        lacks.append("impact metric or outcome (e.g., % improvement)")

    feedback_parts: List[str] = []
    if positives:
        feedback_parts.append("Good: " + "; ".join(positives))
    if lacks:
        feedback_parts.append("Lacks: " + "; ".join(lacks[:3]))
    feedback = " | ".join(feedback_parts) if feedback_parts else "Insufficient information on skills, years of experience, projects, and impact."

    return final_score, feedback
