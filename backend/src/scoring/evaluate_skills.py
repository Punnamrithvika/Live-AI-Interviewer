from __future__ import annotations

"""
Evaluate candidate answers using precomputed artifacts (answers.pt + meta.json).

Artifacts are produced by model_train.py and stored under src/scoring/artifacts/.
Exports the same API consumed by trained_model.py:
 - score_candidate_answer_realtime(question, candidate_answer, question_type="intermediate", top_k=3)
 - score_candidate_answer_with_feedback(question, candidate_answer, question_type="intermediate", top_k=3)
"""

import json
from pathlib import Path
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import re


ROOT = Path(__file__).parent
ART_DIR = ROOT / 'artifacts'
META_PATH = ART_DIR / 'meta.json'
ANSWERS_PATH = ART_DIR / 'answers.pt'


def _load_meta():
    if not META_PATH.exists() or not ANSWERS_PATH.exists():
        raise RuntimeError("Scoring artifacts not found. Run model_train.py to generate meta.json and answers.pt")
    meta = json.loads(META_PATH.read_text(encoding='utf-8'))
    return meta


_meta = _load_meta()
_EMBED_MODEL = _meta.get('embed_model', 'all-MiniLM-L6-v2')
_QA_MODEL = _meta.get('qa_model', 'cross-encoder/ms-marco-MiniLM-L-6-v2')

# Load models (will use local HF cache if available)
_embedder = SentenceTransformer(_EMBED_MODEL, cache_folder=str(ROOT / 'cache'))
_answer_embeddings = torch.load(str(ANSWERS_PATH))

_tokenizer = AutoTokenizer.from_pretrained(_QA_MODEL, cache_dir=str(ROOT / 'cache'))
_qa_model = AutoModelForSequenceClassification.from_pretrained(_QA_MODEL, cache_dir=str(ROOT / 'cache'))


# Stopword preprocessing (simple minimal set to avoid NLTK dependency at runtime)
_STOPWORDS = set(["the","a","an","and","or","but","if","then","is","are","to","of","in"]) 


def _remove_stopwords(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return " ".join([w for w in text.split() if w not in _STOPWORDS])


QUESTION_TYPE_WEIGHT = {
    "basic": 0.8,
    "intermediate": 1.0,
    "advanced": 1.2,
}


def score_candidate_answer_realtime(question: str, candidate_answer: str, question_type: str = "intermediate", top_k: int = 3) -> float:
    # Step 1: Preprocess
    question_filtered = _remove_stopwords(question)
    answer_filtered = _remove_stopwords(candidate_answer)

    overlap_words = set(question_filtered.split()) & set(answer_filtered.split())
    overlap_ratio = len(overlap_words) / max(1, len(set(answer_filtered.split())))
    stopword_penalty = min(overlap_ratio, 1.0)

    # Step 2: Embedding for question
    q_emb = _embedder.encode(question, convert_to_tensor=True)

    # Step 3: Cosine similarity to precomputed answers
    cosine_scores = util.cos_sim(q_emb, _answer_embeddings)[0]
    top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))
    if top_results.values.numel() == 0:
        return 0.0

    # Cross-encoder relevance
    inputs = _tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = _qa_model(**inputs)
        cross_score = torch.sigmoid(outputs.logits)[0][0].item()

    combined = []
    for s in top_results.values:
        val = 0.5 * s.item() + 0.5 * cross_score
        val *= (1 - stopword_penalty)
        combined.append(val)

    final_score = float(np.mean(combined) * 100.0)
    weight = QUESTION_TYPE_WEIGHT.get(question_type.lower(), 1.0)
    final_score *= weight
    final_score = min(final_score, 100.0)
    if final_score < 30:
        return round(final_score, 2)
    else:
        return round(final_score + 20.0, 2)


def score_candidate_answer_with_feedback(question: str, candidate_answer: str, question_type: str = "intermediate", top_k: int = 3):
    qf = _remove_stopwords(question)
    af = _remove_stopwords(candidate_answer)
    overlap_words = set(qf.split()) & set(af.split())
    overlap_ratio = len(overlap_words) / max(1, len(set(af.split())))
    stopword_penalty = min(overlap_ratio, 1.0)

    q_emb = _embedder.encode(question, convert_to_tensor=True)
    cosine_scores = util.cos_sim(q_emb, _answer_embeddings)[0]
    top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))
    if top_results.values.numel() == 0:
        return 0.0, "No relevant content detected."

    max_sim = float(torch.max(top_results.values).item()) if top_results.values.numel() > 0 else 0.0

    inputs = _tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = _qa_model(**inputs)
        cross_score = torch.sigmoid(outputs.logits)[0][0].item()

    combined = []
    for s in top_results.values:
        val = 0.5 * s.item() + 0.5 * cross_score
        val *= (1 - stopword_penalty)
        combined.append(val)

    final_score = float(np.mean(combined) * 100.0)
    weight = QUESTION_TYPE_WEIGHT.get(question_type.lower(), 1.0)
    final_score = min(final_score * weight, 100.0)
    if final_score >= 30:
        final_score = min(final_score + 20.0, 100.0)
    final_score = round(final_score, 2)

    # Feedback
    words_in_answer = len(af.split())
    fb_parts = []
    if words_in_answer < 5:
        fb_parts.append("very brief answer length")
    if overlap_ratio >= 0.5:
        fb_parts.append("high overlap with question wording (possible restatement)")
    if cross_score >= 0.7 and max_sim >= 0.5 and final_score >= 60:
        fb_parts.append("high relevance and alignment with expected content")
    elif cross_score >= 0.5 or max_sim >= 0.4:
        fb_parts.append("partial relevance and coverage of key points")
    else:
        fb_parts.append("low relevance/coverage for the question")

    feedback = "; ".join(fb_parts)
    return final_score, feedback
