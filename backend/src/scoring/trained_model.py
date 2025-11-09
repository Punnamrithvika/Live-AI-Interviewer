"""Primary scoring module.

If standalone artifacts produced by model_train.py exist (meta.json + answers.pt),
we defer to evaluate_skills.py which loads precomputed embeddings. This allows the
application to skip dataset parsing and embedding recomputation at startup.

Fallback: if artifacts are missing, we use the original dynamic pipeline below.
"""

import pandas as pd
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSequenceClassification
try:
    import nltk
    from nltk.corpus import stopwords
except Exception:
    nltk = None
    stopwords = None
import re
import json
import hashlib
from pathlib import Path

# Stopwords: define a safe default at module import so functions never crash
STOP_WORDS_DEFAULT = set([
    "the","a","an","and","or","but","if","then","is","are","to","of","in",
    "on","for","with","as","by","at","from"
])
stop_words = STOP_WORDS_DEFAULT.copy()

# Try to load NLTK stopwords if available; ignore failures silently
try:
    if nltk is not None and stopwords is not None:
        nltk.download('stopwords', quiet=True)
        stop_words = set(stopwords.words('english'))
except Exception:
    # keep default
    pass

# Attempt runtime artifact shortcut
_ARTIFACT_RUNTIME_LOADED = False
try:
    from . import evaluate_skills as _runtime
    # Re-export scoring API and stop here if artifacts available.
    score_candidate_answer_realtime = _runtime.score_candidate_answer_realtime
    score_candidate_answer_with_feedback = _runtime.score_candidate_answer_with_feedback
    _ARTIFACT_RUNTIME_LOADED = True
except Exception:
    # Artifacts not present or failed to load; proceed with dynamic pipeline.
    _ARTIFACT_RUNTIME_LOADED = False

if _ARTIFACT_RUNTIME_LOADED:
    # Skip the rest of dynamic initialization.
    pass
else:
    # Lazy dynamic pipeline (dataset + models). Defers heavyweight loads until first scoring call
    # Module-level lazy holders
    global model_embed, answer_embeddings, tokenizer, qa_model, _INIT_FAILED
    model_embed = None  # type: ignore
    answer_embeddings = None  # type: ignore
    tokenizer = None  # type: ignore
    qa_model = None  # type: ignore

    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    _ROOT = Path(__file__).parent
    _DATA_PATH = _ROOT / "combined_dataset_final.csv"
    _CACHE_DIR = _ROOT / "cache"
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
    QA_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def _cache_paths(dataset_path: Path, embed_model_name: str):
        ds_hash = _sha256_file(dataset_path)
        model_tag = re.sub(r"[^a-zA-Z0-9_\-]", "_", embed_model_name)
        emb_path = _CACHE_DIR / f"answers_{model_tag}_{ds_hash[:16]}.pt"
        meta_path = _CACHE_DIR / f"answers_{model_tag}_{ds_hash[:16]}.json"
        return emb_path, meta_path

    def _load_or_compute_answer_embeddings(df: pd.DataFrame, embedder: SentenceTransformer, dataset_path: Path, embed_model_name: str):
        emb_path, meta_path = _cache_paths(dataset_path, embed_model_name)
        if emb_path.exists() and meta_path.exists():
            try:
                emb = torch.load(str(emb_path))
                with meta_path.open('r', encoding='utf-8') as f:
                    meta = json.load(f)
                if meta.get('model') == embed_model_name and meta.get('count') == len(df['Answer']):
                    return emb
            except Exception:
                pass
        answers = df['Answer'].fillna("").tolist()
        emb = embedder.encode(answers, convert_to_tensor=True, show_progress_bar=False)
        try:
            torch.save(emb, str(emb_path))
            with meta_path.open('w', encoding='utf-8') as f:
                json.dump({"model": embed_model_name, "count": len(answers)}, f)
        except Exception:
            pass
        return emb

    _INIT_FAILED = False

    def _lazy_init():
        global model_embed, answer_embeddings, tokenizer, qa_model, _INIT_FAILED
        if _INIT_FAILED:
            return
        if model_embed is not None and answer_embeddings is not None and tokenizer is not None and qa_model is not None:
            return
        try:
            if not _DATA_PATH.exists():
                raise FileNotFoundError(f"Dataset not found: {_DATA_PATH}")
            df = pd.read_csv(_DATA_PATH)
            model_embed = SentenceTransformer(EMBED_MODEL_NAME, cache_folder=str(_CACHE_DIR))
            answer_embeddings = _load_or_compute_answer_embeddings(df, model_embed, _DATA_PATH, EMBED_MODEL_NAME)
            tokenizer = AutoTokenizer.from_pretrained(QA_MODEL_NAME, cache_dir=str(_CACHE_DIR))
            qa_model = AutoModelForSequenceClassification.from_pretrained(QA_MODEL_NAME, cache_dir=str(_CACHE_DIR))
        except Exception:
            _INIT_FAILED = True
            # Leave models as None; scoring functions will fallback gracefully.
            pass

# Stopword preprocessing
def remove_stopwords(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    filtered = " ".join([word for word in text.split() if word not in stop_words])
    return filtered

# Weight multipliers for question types
QUESTION_TYPE_WEIGHT = {
    "basic": 0.8,
    "intermediate": 1.0,
    "advanced": 1.2
}

if not _ARTIFACT_RUNTIME_LOADED:
    # Real-time scoring function (dynamic fallback only)
    def score_candidate_answer_realtime(question, candidate_answer, question_type="intermediate", top_k=3):
        # Ensure models are initialized lazily
        try:
            _lazy_init()  # type: ignore
        except Exception:
            pass
        # Step 1: Remove stopwords
        question_filtered = remove_stopwords(question)
        answer_filtered = remove_stopwords(candidate_answer)

        # Penalize if candidate repeats question words
        overlap_words = set(question_filtered.split()) & set(answer_filtered.split())
        overlap_ratio = len(overlap_words) / max(1, len(set(answer_filtered.split())))
        stopword_penalty = min(overlap_ratio, 1.0)  # Max 100% penalty

        # Step 2: Compute question embedding
        if 'model_embed' not in globals() or model_embed is None or answer_embeddings is None:
            # Fallback trivial heuristic when models unavailable
            return 0.0
        question_embedding = model_embed.encode(question, convert_to_tensor=True)

        # Step 3: Cosine similarity with dataset answers
        cosine_scores = util.cos_sim(question_embedding, answer_embeddings)[0]
        top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))

        if top_results.values.numel() == 0:
            return 0.0  # No matching answers

        # Cross-encoder relevance (same for all refs)
        if tokenizer is not None and qa_model is not None:
            inputs = tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
            with torch.no_grad():
                outputs = qa_model(**inputs)
                cross_score = torch.sigmoid(outputs.logits)[0][0].item()
        else:
            cross_score = 0.0

        combined_scores = []
        for score in top_results.values:
            # Step 5: Combine scores
            final_score = 0.5*score.item() + 0.5*cross_score

            # Step 6: Apply stopword penalty
            final_score = final_score * (1 - stopword_penalty)
            combined_scores.append(final_score)

        # Step 7: Scale to 0-100
        final_score_100 = float(np.mean(combined_scores) * 100)

        # Step 8: Apply question type weight
        weight = QUESTION_TYPE_WEIGHT.get(question_type.lower(), 1.0)
        final_score_100 = final_score_100 * weight

        # Cap score at 100
        final_score_100 = min(final_score_100, 100.0)
        if final_score_100 < 30:
            return round(final_score_100, 2)
        else:
            return round(final_score_100+20, 2)


    def score_candidate_answer_with_feedback(question, candidate_answer, question_type="intermediate", top_k=3):
        try:
            _lazy_init()  # type: ignore
        except Exception:
            pass
        """
        Return (score_0_100, feedback_str) using the same pipeline as score_candidate_answer_realtime,
        plus a brief feedback string derived from overlap (bluffing) and relevance signals.
        """
        # Step 1: Remove stopwords
        question_filtered = remove_stopwords(question)
        answer_filtered = remove_stopwords(candidate_answer)

        # Overlap / bluffing signal
        overlap_words = set(question_filtered.split()) & set(answer_filtered.split())
        overlap_ratio = len(overlap_words) / max(1, len(set(answer_filtered.split())))
        stopword_penalty = min(overlap_ratio, 1.0)

        # Step 2: Compute embeddings and similarities
        if 'model_embed' not in globals() or model_embed is None or answer_embeddings is None:
            return 0.0, "Model not initialized"
        question_embedding = model_embed.encode(question, convert_to_tensor=True)
        cosine_scores = util.cos_sim(question_embedding, answer_embeddings)[0]
        top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))
        if top_results.values.numel() == 0:
            return 0.0, "No relevant content detected."

        max_sim = float(torch.max(top_results.values).item()) if top_results.values.numel() > 0 else 0.0

        # Cross-encoder relevance (same for all refs)
        if tokenizer is not None and qa_model is not None:
            inputs = tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
            with torch.no_grad():
                outputs = qa_model(**inputs)
                cross_score = torch.sigmoid(outputs.logits)[0][0].item()
        else:
            cross_score = 0.0

        # Combine across top refs
        combined_scores = []
        for s in top_results.values:
            comp = 0.5*s.item() + 0.5*cross_score
            comp *= (1 - stopword_penalty)
            combined_scores.append(comp)

        final_score_100 = float(np.mean(combined_scores) * 100)
        weight = QUESTION_TYPE_WEIGHT.get(question_type.lower(), 1.0)
        final_score_100 = min(final_score_100 * weight, 100.0)
        if final_score_100 >= 30:
            final_score_100 = min(final_score_100 + 20.0, 100.0)
        final_score_100 = round(final_score_100, 2)

        # Feedback heuristics
        words_in_answer = len(answer_filtered.split())
        fb_parts = []
        if words_in_answer < 5:
            fb_parts.append("very brief answer length")
        if overlap_ratio >= 0.5:
            fb_parts.append("high overlap with question wording (possible restatement)")
        # Relevance buckets from cross-encoder & similarity
        if cross_score >= 0.7 and max_sim >= 0.5 and final_score_100 >= 60:
            fb_parts.append("high relevance and alignment with expected content")
        elif cross_score >= 0.5 or max_sim >= 0.4:
            fb_parts.append("partial relevance and coverage of key points")
        else:
            fb_parts.append("low relevance/coverage for the question")

        feedback = "; ".join(fb_parts)
        return final_score_100, feedback


