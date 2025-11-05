"""
Project answer evaluation supporting three modes:

1) Semantic similarity (fast, reliable): cosine similarity to reference answers using
   sentence-transformers (default model: all-MiniLM-L6-v2), mapped to 0–100.

2) LLM-based rubric (context-aware): asks the LLM to score per rubric and return JSON
   with {"score": <0..100>, "feedback": "..."}.

3) Hybrid (default): 50% semantic + 50% LLM rubric. Falls back gracefully if a method
   is unavailable (e.g., missing packages or API keys).

Configure via env:
- PROJECT_EVAL_METHOD: similarity | llm | hybrid (default: hybrid)
- PROJECT_EVAL_SIM_MODEL: sentence-transformers model name (default: all-MiniLM-L6-v2)
"""

from __future__ import annotations

import json
import math
import os
from typing import List, Optional, Tuple


# Lightweight references to anchor semantic similarity
_REFERENCE_PROJECT_ANSWERS: List[str] = [
    # Backend microservices archetype
    (
        "I designed and led a microservices-based backend handling high traffic."
        " We used Python (FastAPI), PostgreSQL, Redis caching, and Kafka for async events."
        " I implemented an API gateway, service-to-service auth, and observability."
        " We improved p95 latency by over 30% and scaled to thousands of RPS."
    ),
    # Data/streaming pipeline archetype
    (
        "I owned a real-time data pipeline with Kafka and Spark, implementing exactly-once semantics,"
        " schema evolution, and backpressure handling. I optimized batch and stream jobs and"
        " reduced processing time while ensuring data quality with tests and monitoring."
    ),
    # Full‑stack web app archetype
    (
        "I built an end-to-end web application with React on the frontend and Node.js/Express + PostgreSQL"
        " on the backend. I added authentication, role-based access, CI/CD pipelines, and integration tests,"
        " focusing on UX and performance improvements backed by metrics."
    ),
]


_st_model = None
_ref_embeddings = None


def _lazy_load_st_model(model_name: str):
    global _st_model
    if _st_model is not None:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception:
        return None
    try:
        _st_model = SentenceTransformer(model_name)
        return _st_model
    except Exception:
        return None


def _semantic_similarity_score(answer: str, model_name: Optional[str] = None) -> Optional[float]:
    """Return 0..100 similarity score or None if unavailable."""
    if not answer or not answer.strip():
        return 0.0
    # Respect env override, default to all-MiniLM-L6-v2
    model_name = model_name or os.getenv("PROJECT_EVAL_SIM_MODEL", "all-MiniLM-L6-v2")
    model = _lazy_load_st_model(model_name)
    if model is None:
        return None
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None

    global _ref_embeddings
    try:
        if _ref_embeddings is None:
            _ref_embeddings = model.encode(_REFERENCE_PROJECT_ANSWERS, convert_to_tensor=False)
        ans_emb = model.encode([answer.strip()], convert_to_tensor=False)[0]
        # Cosine similarity to each reference, take max
        sims = []
        for ref in _ref_embeddings:
            denom = (np.linalg.norm(ans_emb) * np.linalg.norm(ref)) or 1e-6
            sims.append(float(np.dot(ans_emb, ref) / denom))
        sim = max(sims) if sims else 0.0
        # Map cosine [-1,1] to [0,100] focusing on [0,1]
        sim01 = (sim + 1.0) / 2.0
        return max(0.0, min(100.0, sim01 * 100.0))
    except Exception:
        return None


def _llm_rubric_score(answer: str, question: Optional[str] = None, expected_skills: Optional[List[str]] = None) -> Tuple[Optional[float], Optional[str]]:
    """Ask LLM to score per rubric; return (0..100, feedback) or (None, None) if LLM unavailable."""
    if not answer or not answer.strip():
        return 0.0, "Answer is empty."
    try:
        # Local import to avoid hard dependency if cohere isn't configured
        from ..utils.cohere_client import generate_text  # type: ignore
    except Exception:
        return None, None

    rubric = (
        "Evaluate the candidate's project answer. Score 0-100 strictly as integer."
        " Criteria: 1) Technical depth 2) Clarity & structure 3) Relevance to project"
        " 4) Personal contribution/ownership."
        " In 'feedback', provide brief reasons that justify the score (strengths and what is missing)."
        " Do not give advice or suggestions; reasons-only."
    )
    q_part = f"Project question: {question}\n" if question else ""
    # Explicitly exclude expected skills from the prompt per request.
    prompt = (
        f"{q_part}Candidate answer:\n" + answer.strip() + "\n\n"
        "Return JSON strictly as {\"score\": <0..100>, \"feedback\": \"...\"}."
    )
    try:
        raw = generate_text(prompt, system=rubric, json_mode=True)
        data = json.loads(raw)
        score = data.get("score")
        feedback = data.get("feedback")
        if isinstance(score, (int, float)):
            return max(0.0, min(100.0, float(score))), (str(feedback) if feedback else None)
    except Exception:
        # Fall through to None
        return None, None
    return None, None


def _fallback_heuristic(answer: str) -> float:
    """Very light, dependency-free heuristic used as last resort (0..100)."""
    a = (answer or "").lower()
    score = 0
    # Count tech-ish tokens
    tech_terms = [
        "python", "java", "node", "react", "django", "fastapi", "spring", "postgres", "redis", "kafka",
        "docker", "kubernetes", "ci/cd", "github actions", "microservices", "rest", "graphql",
    ]
    score += min(10, sum(1 for t in tech_terms if t in a)) * 5  # up to 50
    # Ownership verbs
    if any(x in a for x in ["led", "owned", "architected", "designed", "delivered"]):
        score += 10
    # Impact words / numbers
    if any(x in a for x in ["%", "latency", "rps", "throughput", "users", "ms"]):
        score += 10
    # Testing/CI
    if any(x in a for x in ["unit test", "integration test", "pipeline", "ci/cd", "github actions", "jenkins"]):
        score += 10
    # Length bonus
    n = len(a.split())
    if n > 120:
        score += 10
    elif n > 60:
        score += 8
    elif n > 30:
        score += 6
    elif n > 15:
        score += 4
    return float(max(0, min(100, score)))


def evaluate_project_answer(answer_text: str) -> Tuple[int, str]:
    method = os.getenv("PROJECT_EVAL_METHOD", "hybrid").lower()

    # Optional context could be added in future by changing signature or reading from store
    question: Optional[str] = None
    expected_skills: Optional[List[str]] = None

    sim = _semantic_similarity_score(answer_text)
    llm_score, llm_feedback = _llm_rubric_score(answer_text, question=question, expected_skills=expected_skills)

    feedback_fragments: List[str] = []
    if method == "similarity":
        score = sim if sim is not None else _fallback_heuristic(answer_text)
        if sim is not None:
            feedback_fragments.append(f"Similarity-based score: {int(round(sim))}")
    elif method == "llm":
        score = llm_score if llm_score is not None else (sim if sim is not None else _fallback_heuristic(answer_text))
        if llm_feedback:
            feedback_fragments.append(f"LLM: {llm_feedback}")
    else:  # hybrid
        # If only one is available, use it; else average
        if sim is not None and llm_score is not None:
            score = 0.5 * sim + 0.5 * llm_score
            feedback_fragments.append(f"Similarity: {int(round(sim))}")
            if llm_feedback:
                feedback_fragments.append(f"LLM: {llm_feedback}")
        elif sim is not None:
            score = sim
            feedback_fragments.append(f"Similarity-based score: {int(round(sim))}")
        elif llm_score is not None:
            score = llm_score
            if llm_feedback:
                feedback_fragments.append(f"LLM: {llm_feedback}")
        else:
            score = _fallback_heuristic(answer_text)

    # Heuristic suggestions for missing aspects
    a = (answer_text or "").lower()
    aspects = {
        "architecture/design": any(x in a for x in ["architecture", "design", "pattern", "microservice", "monolith", "scalable", "scalability"]),
        "trade-offs/decisions": any(x in a for x in ["trade-off", "tradeoff", "chose", "decided", "because"]),
        "testing/quality": any(x in a for x in ["test", "unit", "integration", "e2e", "qa"]),
        "metrics/impact": any(x in a for x in ["%", "latency", "rps", "throughput", "error rate", "p95", "users", "ms"]),
        "ownership": any(x in a for x in ["led", "owned", "architected", "designed", "delivered", "implemented"]),
    }
    missing = [k for k, v in aspects.items() if not v]
    if missing:
        feedback_fragments.append("Low coverage: " + ", ".join(missing[:3]))

    final_score = int(round(max(0.0, min(100.0, float(score)))))
    feedback = " | ".join(feedback_fragments) if feedback_fragments else "Low coverage across architecture, decisions, testing, metrics, and ownership."
    return final_score, feedback
