# AI Interview System — Backend

Backend system that conducts automated interviews in three phases: Introduction, Projects, Skills. Powered by Cohere LLM, gTTS (Google TTS), and Google Speech Recognition (STT). Generates a PDF report.

## Setup

1. Python 3.10+ recommended on Windows.
2. Create and fill `.env` in `backend/`:

```
COHERE_API_KEY=YOUR_COHERE_API_KEY
```

3. Install dependencies (PowerShell):

```
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r backend\requirements.txt
```

4. Speech-to-Text (STT) configuration:

   - The frontend converts mic audio to 16kHz mono WAV before upload to avoid server ffmpeg dependency.
   - If the browser sends non-WAV (rare fallback), ffmpeg is required server-side to transcode.
   - You can control STT via environment variables in `.env`:
     - `STT_ENGINE=google` (default) uses free Google Web Speech API (rate/length limited)
     - `STT_ENGINE=google_cloud` uses Google Cloud STT; set `GOOGLE_CLOUD_SPEECH_CREDENTIALS` to the JSON string of your service account credentials
     - `STT_LANGUAGE=en-US` (default), e.g., `en-IN`, `en-GB`, etc.
   - If STT fails, the UI prompts the candidate to type their answer so the interview can continue.

   Optional ffmpeg installation (for non-WAV uploads):

   - See `../SETUP_FFMPEG.md` for installation instructions
   - Without ffmpeg, only WAV uploads will be transcribed

Notes for Windows:

- `PyAudio` may require wheel installation. If `pip install pyaudio` fails, download a matching wheel from a reputable source (e.g., Gohlke) and install: `pip install <wheel.whl>`.
- `playsound` is best-effort for MP3 playback. If it fails, the MP3 is still saved in `backend/audio_out/`. You can open it manually.

## Run (basic, interactive with mic)

```
python backend\main.py --name "Jane Doe" --role "Backend Engineer" --skills "python,system design" --resume "C:\\path\\to\\resume.pdf"
```

Use `--no-audio` to skip playback (useful for CI/testing).

## What it does

- Extracts text from resume (.pdf via PyMuPDF, .docx via python-docx)
- Uses Cohere to summarize projects as JSON
- Intro phase: asks for a self-introduction
- Projects phase: generates 3 questions
- Skills phase: adaptive levels (basic → intermediate → advanced), 3 questions per level
- Evaluates answers via simple placeholders + `src/scoring/trained.py` wrapper
- Stores session data in `backend/data/` and generates a PDF report in `backend/reports/`

## Extending scoring

Implement `score(question, answer, context=None)` in `src/scoring/trained_model.py` to return a 0–100 score. The wrapper in `trained.py` will call it when present.

## Project structure

See comments in each module. Entry point is `backend/main.py` which uses `InterviewController`.

## Offline training and faster runtime

To avoid recomputing embeddings at runtime, you can prebuild scoring artifacts:

1. Train/build artifacts (PowerShell):

```
.\.venv\Scripts\Activate.ps1
python backend\src\scoring\model_train.py --dataset backend\src\scoring\combined_dataset_final.csv --out backend\src\scoring\artifacts
```

This creates `meta.json` and `answers.pt` under `backend/src/scoring/artifacts/`.

2. Runtime behavior:

- `src/scoring/trained_model.py` now auto-detects these artifacts and delegates to `src/scoring/evaluate_skills.py`.
- If artifacts are missing, it falls back to the dynamic path that loads the dataset and computes embeddings on the fly (with caching under `src/scoring/cache/`).

3. Optional settings:

- Models are cached under `backend/src/scoring/cache/` by default to speed up subsequent runs.

## Quick sanity checks

Run lightweight checks without starting the server:

- STT smoke test (offline, no mic required):

  ```
  python backend\tests\test_stt_smoke.py
  ```

- Report generation integrity (PDF or .txt fallback):

  ```
  python backend\tests\test_report_generation.py
  ```
