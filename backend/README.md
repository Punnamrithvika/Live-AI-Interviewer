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

4. **(Optional but recommended)** Install ffmpeg for audio transcription:
   - See `../SETUP_FFMPEG.md` for installation instructions
   - Without ffmpeg, transcription will fall back to typed input

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
