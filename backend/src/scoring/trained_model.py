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
from pathlib import Path

# Download stopwords once (robust to offline). If nltk unavailable, use a small built-in set.
try:
    if nltk is not None and stopwords is not None:
        nltk.download('stopwords', quiet=True)
        stop_words = set(stopwords.words('english'))
    else:
        # Minimal fallback set
        stop_words = set(["the","a","an","and","or","but","if","then","is","are","to","of","in"]) 
except Exception:
    stop_words = set()

# Load dataset (relative to this file)
_DATA_PATH = Path(__file__).parent / "combined_dataset_final.csv"
df = pd.read_csv(_DATA_PATH)  # Ensure it has 'Question' and 'Answer' columns

# Precompute embeddings for dataset answers
model_embed = SentenceTransformer('all-MiniLM-L6-v2')
answer_embeddings = model_embed.encode(df['Answer'].tolist(), convert_to_tensor=True)

# Load cross-encoder for relevance scoring
qa_model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
tokenizer = AutoTokenizer.from_pretrained(qa_model_name)
qa_model = AutoModelForSequenceClassification.from_pretrained(qa_model_name)

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

# Real-time scoring function
def score_candidate_answer_realtime(question, candidate_answer, question_type="intermediate", top_k=3):
    # Step 1: Remove stopwords
    question_filtered = remove_stopwords(question)
    answer_filtered = remove_stopwords(candidate_answer)

    # Penalize if candidate repeats question words
    overlap_words = set(question_filtered.split()) & set(answer_filtered.split())
    overlap_ratio = len(overlap_words) / max(1, len(set(answer_filtered.split())))
    stopword_penalty = min(overlap_ratio, 1.0)  # Max 100% penalty

    # Step 2: Compute question embedding
    question_embedding = model_embed.encode(question, convert_to_tensor=True)

    # Step 3: Cosine similarity with dataset answers
    cosine_scores = util.cos_sim(question_embedding, answer_embeddings)[0]
    top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))

    if top_results.values.numel() == 0:
        return 0.0  # No matching answers

    # Cross-encoder relevance (same for all refs)
    inputs = tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = qa_model(**inputs)
        cross_score = torch.sigmoid(outputs.logits)[0][0].item()

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
    question_embedding = model_embed.encode(question, convert_to_tensor=True)
    cosine_scores = util.cos_sim(question_embedding, answer_embeddings)[0]
    top_results = torch.topk(cosine_scores, k=min(top_k, len(cosine_scores)))
    if top_results.values.numel() == 0:
        return 0.0, "No relevant content detected."

    max_sim = float(torch.max(top_results.values).item()) if top_results.values.numel() > 0 else 0.0

    # Cross-encoder relevance (same for all refs)
    inputs = tokenizer([question], [candidate_answer], return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = qa_model(**inputs)
        cross_score = torch.sigmoid(outputs.logits)[0][0].item()

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


