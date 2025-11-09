from __future__ import annotations

"""
Offline trainer to prepare scoring artifacts once and reuse during evaluation.

Artifacts written to: src/scoring/artifacts/
 - meta.json: { embed_model, qa_model, dataset_sha256, count, answers_path }
 - answers.pt: torch tensor of precomputed embeddings for dataset 'Answer' column

Run (from repo root):
  python -m backend.src.scoring.model_train \
    --dataset backend/src/scoring/combined_dataset_final.csv \
    --embed-model all-MiniLM-L6-v2 \
    --qa-model cross-encoder/ms-marco-MiniLM-L-6-v2
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def train_and_save(dataset_path: Path, embed_model: str, qa_model: str) -> Path:
    root = Path(__file__).parent
    artifacts_dir = root / 'artifacts'
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(dataset_path)
    if 'Answer' not in df.columns:
        raise ValueError("Dataset must contain an 'Answer' column")

    print(f"[train] Loading embedder: {embed_model}")
    embedder = SentenceTransformer(embed_model, cache_folder=str(root / 'cache'))
    answers = df['Answer'].fillna('').tolist()
    print(f"[train] Encoding {len(answers)} answers...")
    emb = embedder.encode(answers, convert_to_tensor=True, show_progress_bar=True)

    answers_path = artifacts_dir / 'answers.pt'
    torch.save(emb, str(answers_path))

    meta = {
        'embed_model': embed_model,
        'qa_model': qa_model,
        'dataset_sha256': sha256_file(dataset_path),
        'count': len(answers),
        'answers_path': 'answers.pt',
        'dataset_name': dataset_path.name,
    }
    meta_path = artifacts_dir / 'meta.json'
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f"[train] Saved artifacts -> {artifacts_dir}")
    return artifacts_dir


def main():
    p = argparse.ArgumentParser(description='Prepare scoring artifacts (embeddings cache).')
    p.add_argument('--dataset', type=str, default=str(Path(__file__).parent / 'combined_dataset_final.csv'))
    p.add_argument('--embed-model', type=str, default='all-MiniLM-L6-v2')
    p.add_argument('--qa-model', type=str, default='cross-encoder/ms-marco-MiniLM-L-6-v2')
    args = p.parse_args()

    ds = Path(args.dataset)
    if not ds.exists():
        raise SystemExit(f"Dataset not found: {ds}")
    train_and_save(ds, args.embed_model, args.qa_model)


if __name__ == '__main__':
    main()
