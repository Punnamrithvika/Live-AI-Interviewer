import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Optional

# Ensure backend directory is on sys.path so `src` package imports work when running this module directly
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time

from src.utils.storage import SessionStore
from src.extraction.resume_extractor import extract_resume_text, summarize_projects_from_resume_text
from src.questions.introduction_phase import generate_intro_question
# switched to single-question generation on demand
from src.scoring.evaluate_intro import evaluate_intro_answer
from src.scoring.evaluate_project import evaluate_project_answer
from src.scoring import trained_model
from src.utils.report_generator import generate_report
from src.utils.cohere_client import generate_text
from src.utils.file_utils import VIDEO_DIR, sanitize_filename, timestamp
from src.questions.skills_phase import generate_distinct_skill_question, normalize_question

app = FastAPI(title="AI Interview Adapter")

# CORS (allow frontend dev server and same-origin calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # consider restricting to http://localhost:3000 in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic request logging middleware
logger = logging.getLogger("uvicorn.error")

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("Error while handling %s %s", request.method, request.url)
        raise
    finally:
        dur_ms = int((time.time() - start) * 1000)
        logger.info("%s %s -> %d ms", request.method, request.url.path, dur_ms)

# Catch-all exception handler to return JSON and log stack traces
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})

# In-memory sessions mapping: session_id -> session dict
SESSIONS: Dict[str, Dict] = {}


def _create_session(candidate_name: str, job_title: str) -> SessionStore:
    store = SessionStore(candidate_name, job_title)
    return store


"""
Skill question distinctness helpers are now in src.questions.skills_phase.
We import generate_distinct_skill_question and normalize_question above.
"""


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    # Save to a temp file and extract text
    suffix = Path(file.filename).suffix or ".pdf"
    tmp = Path(tempfile.gettempdir()) / f"resume_{uuid.uuid4().hex}{suffix}"
    with tmp.open("wb") as f:
        content = await file.read()
        f.write(content)
    try:
        text = extract_resume_text(str(tmp))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    projects = summarize_projects_from_resume_text(text)
    return {"success": True, "data": {"raw_text": text, "projects": projects}}


@app.post("/api/start-interview")
async def start_interview(payload: Dict):
    # Expected fields: candidate_name, job_title, recruiter_skills, target_skill_difficulties, resume_text (optional), projects (optional)
    cname = payload.get("candidate_name")
    role = payload.get("job_title") or "Role"
    if not cname:
        raise HTTPException(status_code=400, detail="candidate_name is required")

    store = _create_session(cname, role)

    # Populate projects if provided (frontend may send resume_text or projects)
    projects = payload.get("projects")
    if not projects and payload.get("resume_text"):
        try:
            projects = summarize_projects_from_resume_text(payload.get("resume_text"))
        except Exception:
            projects = []

    # Persist projects (empty list if none) into session state for consistency
    store.add_project_summaries(projects or [])

    try:
        logger.info(
            "start-interview: candidate=%s role=%s projects=%d resume_text=%s titles=%s",
            cname,
            role,
            len(projects or []),
            "yes" if bool(payload.get("resume_text")) else "no",
            [ (p or {}).get("project_title") for p in (projects or []) ][:3],
        )
    except Exception:
        pass

    # Create session entry
    session_id = store.session_id
    first_question = generate_intro_question(cname)
    SESSIONS[session_id] = {
        "store": store,
        "phase": "introduction",
        "pending_project_questions": [],
        "project_index": 0,
        "skills_queue": payload.get("recruiter_skills", []),
        "skill_state": {"idx": 0, "level_idx": 0, "levels": ["basic", "intermediate", "advanced"]},
        # Map of skill -> target level (default advanced if not provided)
        "skill_targets": payload.get("target_skill_difficulties", {}) or {},
        # Per-level counters for the current skill/level
        "level_counters": {"asked": 0, "passes": 0, "fails": 0},
    }

    return {"success": True, "session_id": session_id, "question": first_question}


@app.post("/api/send-message")
async def send_message(payload: Dict):
    session_id = payload.get("session_id")
    message = payload.get("message")
    if not session_id or session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = SESSIONS[session_id]
    store: SessionStore = sess["store"]
    phase = sess.get("phase", "introduction")

    # Helper to return final response with next question
    def _resp(success: bool, question: Optional[str], evaluation: Dict = None):
        # Frontend expects next_question: { question: str } for follow-ups
        payload_out: Dict = {"success": success, "session_id": session_id, "evaluation": evaluation}
        if question is not None:
            payload_out["next_question"] = {"question": question}
            payload_out["question"] = question  # keep legacy for other callers
        else:
            payload_out["next_question"] = None
        return payload_out

    if phase == "introduction":
        # Use evaluate_intro_answer
        score, feedback = evaluate_intro_answer(message)
        # store the QA (intro question text isn't persisted; use a generic label)
        q_text = "Introduction"
        store.add_qa("introduction", q_text, message, score, feedback)

        # Prepare project questions
        projects = store.state.get("projects", [])
        try:
            logger.info(
                "intro->projects: session=%s projects_count=%d titles=%s",
                session_id,
                len(projects or []),
                [ (p or {}).get("project_title") for p in (projects or []) ][:3],
            )
        except Exception:
            pass
        # Generate only ONE project question now (on-demand), not a batch
        try:
            from src.questions.projects_phase import generate_project_question_for_one
        except Exception:
            generate_project_question_for_one = None  # type: ignore
        prev_responses = store.get_last_responses("introduction", n=2)
        # Track which projects have been asked
        asked_projects = sess.get("asked_projects", []) or []
        # Pick first unasked project, else first project
        selected = None
        for p in (projects or []):
            title = (p or {}).get("project_title")
            if title and title not in asked_projects:
                selected = p
                break
        if selected is None:
            selected = (projects or [{}])[0] if projects else {"project_title": "", "summary": "recent work"}

        # Generate single question with LLM fallback
        if generate_project_question_for_one is not None:
            next_q = generate_project_question_for_one(selected, prev_responses)
        else:
            title = (selected.get("project_title") or "this project").strip() or "this project"
            next_q = f"In {title}, what was the most difficult technical issue you solved and how?"

        # Init project tracking state
        sess["phase"] = "projects"
        sess["pending_project_questions"] = [next_q]  # keep shape for UI compatibility
        sess["project_index"] = 0
        sess["asked_projects"] = asked_projects
        # target number of project questions before moving to skills
        sess["projects_target"] = max(1, min(3, len(projects) if projects else 1))
        sess["projects_asked"] = 0
        # remember which project this question refers to (lightweight)
        sess["current_project_title"] = (selected or {}).get("project_title")
        return _resp(True, next_q, {"score": score, "feedback": feedback})

    if phase == "projects":
        # get current question (for logging/record)
        idx = int(sess.get("project_index", 0))
        q_list = sess.get("pending_project_questions", []) or []
        q = q_list[idx] if idx < len(q_list) else sess.get("last_project_question") or "Project question"
        # evaluate current project answer
        score, feedback = evaluate_project_answer(message)
        store.add_qa("projects", q, message, score, feedback)
        # increment counters
        sess["projects_asked"] = int(sess.get("projects_asked", 0)) + 1
        asked_projects = sess.get("asked_projects", []) or []
        cur_title = sess.get("current_project_title")
        if cur_title and cur_title not in asked_projects:
            asked_projects.append(cur_title)
        sess["asked_projects"] = asked_projects

        # decide to continue with another single project question or move to skills
        target = int(sess.get("projects_target", 3))
        projects = store.state.get("projects", [])
        # If we still have quota to ask project questions and there exists an unasked project, generate next
        if sess["projects_asked"] < target and (projects or []):
            try:
                from src.questions.projects_phase import generate_project_question_for_one
            except Exception:
                generate_project_question_for_one = None  # type: ignore
            # Select next unasked project; if none, reuse any
            next_selected = None
            for p in (projects or []):
                t = (p or {}).get("project_title")
                if t and t not in asked_projects:
                    next_selected = p
                    break
            if next_selected is None:
                # rotate through projects
                next_selected = projects[(len(asked_projects)) % len(projects)] if projects else {"project_title": "", "summary": "recent work"}
            prev_responses = store.get_last_responses("projects", n=2)
            if generate_project_question_for_one is not None:
                next_q = generate_project_question_for_one(next_selected, prev_responses)
            else:
                title = (next_selected.get("project_title") or "this project").strip() or "this project"
                next_q = f"In {title}, what was the most difficult technical issue you solved and how?"
            sess["pending_project_questions"] = [next_q]
            sess["project_index"] = 0
            sess["current_project_title"] = (next_selected or {}).get("project_title")
            sess["last_project_question"] = next_q
            return _resp(True, next_q, {"score": score, "feedback": feedback})

        # Otherwise, move to skills
        sess["phase"] = "skills"
        # initialize skill pointer
        sess["skill_state"] = {"idx": 0, "level_idx": 0, "levels": ["basic", "intermediate", "advanced"]}
        sess["level_counters"] = {"asked": 0, "passes": 0, "fails": 0}
        # generate first skill question
        skills = sess.get("skills_queue", [])
        if not skills:
            # no skills configured -> end
            sess["phase"] = "done"
            return _resp(True, None, {"score": score, "feedback": feedback})
        cur_skill = skills[0]
        level = sess["skill_state"]["levels"][0]
        from src.questions.skills_phase import _make_skill_prompt

        # Attempt LLM generation; if it fails, surface a structured error instead of injecting a placeholder.
        try:
            next_q = generate_distinct_skill_question(cur_skill, level, store, max_attempts=5)
        except Exception as e:
            return _resp(False, None, {
                "error": "skill_question_generation_failed",
                "detail": str(e),
                "skill": cur_skill,
                "level": level,
                "action": "retry",
            })

        # Persist last skill question for proper scoring on next answer
        sess["last_skill_question"] = next_q
        sess["last_skill_skill"] = cur_skill
        sess["last_skill_level"] = level
        # Reset counters for this level
        sess["level_counters"] = {"asked": 1, "passes": 0, "fails": 0}

        return _resp(True, next_q, {"score": score, "feedback": feedback})

    if phase == "skills":
        # Evaluate with trained model feedback if available
        skill_state = sess.get(
            "skill_state", {"idx": 0, "level_idx": 0, "levels": ["basic", "intermediate", "advanced"]}
        )
        skills = sess.get("skills_queue", [])
        if skill_state["idx"] >= len(skills):
            sess["phase"] = "done"
            return _resp(True, None, {})

        cur_skill = skills[skill_state["idx"]]
        level = skill_state["levels"][skill_state["level_idx"]]

        # Determine the question text that was actually asked last
        q_text = sess.pop("last_skill_question", None)
        if not q_text:
            q_text = f"Skill: {cur_skill} Level: {level}"

        # Use trained_model scorer with feedback if available
        try:
            score, fb = trained_model.score_candidate_answer_with_feedback(q_text, message, question_type=level)
        except Exception:
            # Fallback to realtime scorer
            score = trained_model.score_candidate_answer_realtime(q_text, message, question_type=level)
            fb = None

        store.add_qa("skills", q_text, message, score, fb)
        # Update counters
        counters = sess.get("level_counters", {"asked": 0, "passes": 0, "fails": 0})
        counters["asked"] = int(counters.get("asked", 0)) + 1
        if score >= 30:
            counters["passes"] = int(counters.get("passes", 0)) + 1
        else:
            counters["fails"] = int(counters.get("fails", 0)) + 1

        # Decide whether current level is complete
        level_complete = counters["passes"] >= 2 or counters["fails"] >= 2 or counters["asked"] >= 3
        # Determine target level for this skill (default = advanced)
        targets = sess.get("skill_targets", {}) or {}
        target_level = (targets.get(cur_skill) or "advanced").lower()
        level_order = skill_state["levels"]
        # Helper
        def finalize_level(passed: bool):
            # Persist per-level result into skills_summary
            store.add_skill_result(cur_skill, level, passed, {
                "passes": counters["passes"],
                "fails": counters["fails"],
                "asked": counters["asked"],
                "feedback": (fb or ("Passed" if passed else "Below threshold"))
            })

        advanced_next = False
        move_next_skill = False
        if level_complete:
            passed_level = counters["passes"] >= 2
            finalize_level(passed_level)
            if passed_level:
                # If target reached, move to next skill; else advance to next level
                if level == target_level:
                    move_next_skill = True
                else:
                    skill_state["level_idx"] += 1
                    if skill_state["level_idx"] >= len(level_order):
                        move_next_skill = True
                    else:
                        advanced_next = True
            else:
                # Failed this level -> move to next skill
                move_next_skill = True

            if move_next_skill:
                skill_state["idx"] += 1
                skill_state["level_idx"] = 0
                counters = {"asked": 0, "passes": 0, "fails": 0}
            elif advanced_next:
                counters = {"asked": 0, "passes": 0, "fails": 0}

        sess["skill_state"] = skill_state
        sess["level_counters"] = counters

        # Determine next question or finish
        if skill_state["idx"] >= len(skills):
            sess["phase"] = "done"
            return _resp(True, None, {"score": score, "feedback": fb})
        next_skill = skills[skill_state["idx"]]
        next_level = skill_state["levels"][skill_state["level_idx"]]
        from src.questions.skills_phase import _make_skill_prompt

        try:
            next_q = generate_distinct_skill_question(next_skill, next_level, store, max_attempts=5)  # type: ignore
        except Exception as e:
            return _resp(False, None, {
                "error": "skill_question_generation_failed",
                "detail": str(e),
                "skill": next_skill,
                "level": next_level,
                "action": "retry",
            })

        # Persist last skill question for proper scoring
        sess["last_skill_question"] = next_q
        sess["last_skill_skill"] = next_skill
        sess["last_skill_level"] = next_level
        # Increment asked if starting a new level
        counters = sess.get("level_counters", {"asked": 0, "passes": 0, "fails": 0})
        if counters["asked"] == 0:
            counters["asked"] = 1
        sess["level_counters"] = counters

        return _resp(True, next_q, {"score": score, "feedback": fb})

    return _resp(False, None, {})


@app.get("/api/interview-status/{session_id}")
async def interview_status(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    sess = SESSIONS[session_id]
    return {"success": True, "phase": sess.get("phase"), "session_id": session_id}


@app.get("/api/interview-results/{session_id}")
async def interview_results(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    store: SessionStore = SESSIONS[session_id]["store"]
    state = store.state

    # Transform to frontend 'results' shape
    evaluations = []
    qnum = 1
    for phase_name in ("introduction", "projects", "skills"):
        items = state.get("phases", {}).get(phase_name, []) or []
        for it in items:
            ev = {
                "question_number": qnum,
                "question": it.get("question"),
                "answer": it.get("answer"),
                "score": it.get("score", 0),
                "feedback": it.get("feedback"),
            }
            # Best effort parse for skills: "Skill: X Level: Y" -> skill/difficulty
            qtext = (it.get("question") or "")
            if phase_name == "skills" and qtext.startswith("Skill:"):
                try:
                    # naive parse
                    parts = qtext.split("Level:")
                    skill = parts[0].replace("Skill:", "").strip()
                    level = parts[1].strip() if len(parts) > 1 else None
                    if skill:
                        ev["skill"] = skill
                    if level:
                        ev["difficulty"] = level
                except Exception:
                    pass
            evaluations.append(ev)
            qnum += 1

    # Skills breakdown from skills_summary
    skills_breakdown = {}
    for skill, levels in (state.get("skills_summary", {}) or {}).items():
        questions_asked = sum(int(v.get("asked", 0)) for v in levels.values())
        passes = sum(int(v.get("passes", 0)) for v in levels.values())
        fails = sum(int(v.get("fails", 0)) for v in levels.values())
        total = passes + fails if (passes + fails) > 0 else 1
        percentage = max(0.0, min(100.0, (passes / total) * 100.0))
        # highest difficulty passed or last level present
        level_order = ["basic", "intermediate", "advanced"]
        highest = None
        for lvl in level_order[::-1]:
            if lvl in levels:
                highest = lvl
                break
        target_reached = bool(levels.get("advanced", {}).get("passed", False))
        skills_breakdown[skill] = {
            "questions_asked": questions_asked,
            "percentage_score": percentage,
            "highest_difficulty": highest or "basic",
            "target_reached": target_reached,
        }

    results = {
        "summary": {
            "candidate_name": state.get("candidate", {}).get("name"),
            "job_title": state.get("candidate", {}).get("role"),
            "total_questions": len(evaluations),
            "total_answers": len(evaluations),
        },
        "evaluations": evaluations,
        "skills_breakdown": skills_breakdown,
        # Include projects to help verify persistence in UI/debug tools (unused by UI otherwise)
        "projects": state.get("projects", []),
    }
    return {"success": True, "results": results}


@app.get("/api/llm-health")
async def llm_health():
    """Quick check for LLM availability and latency."""
    import time
    try:
        from src.utils.cohere_client import generate_text, get_client
    except Exception as e:
        return {"ok": False, "where": "import", "error": str(e)}
    try:
        client = get_client()
        model = (getattr(client, "model", None) or os.getenv("LLM_MODEL") or os.getenv("COHERE_MODEL") or "command-r-plus")
    except Exception as e:
        return {"ok": False, "where": "client", "error": str(e)}
    t0 = time.time()
    try:
        text = generate_text("Reply: ok")
        dt = time.time() - t0
        return {"ok": True, "model": str(model), "latency_ms": int(dt * 1000), "sample": (text or "")[:60]}
    except Exception as e:
        dt = time.time() - t0
        return {"ok": False, "where": "chat", "latency_ms": int(dt * 1000), "error": str(e)}


@app.get("/api/dev/skill-question")
async def dev_skill_question(skill: str, level: str = "basic"):
    """Development helper: generate a single distinct skill question for quick testing.

    Returns { ok, question } or { ok: false, error, detail } without mutating any session state.
    """
    try:
        # Create a transient in-memory store to supply recent context shape
        store = SessionStore("DevTester", "DevRole")
        q = generate_distinct_skill_question(skill, level, store, max_attempts=5)
        return {"ok": True, "question": q}
    except Exception as e:
        return {"ok": False, "error": "skill_question_generation_failed", "detail": str(e)}


@app.post("/api/upload-video")
async def upload_video(session_id: Optional[str] = Form(None), file: UploadFile = File(...)):
    """Persist a recorded WebM (or MP4) chunk to disk in video_out.

    Frontend should send FormData with 'file' and optional 'session_id'.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    sid = sanitize_filename(session_id or "nosession")
    ext = ".webm"
    original = (file.filename or "video.webm").lower()
    if original.endswith(".mp4"):
        ext = ".mp4"
    fname = f"{sid}_{timestamp()}{ext}"
    path = VIDEO_DIR / sanitize_filename(fname)
    try:
        with path.open("wb") as f:
            f.write(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store video: {e}")
    return {"success": True, "filename": path.name, "url": f"/api/video/{path.name}"}


@app.get("/api/video/{filename}")
async def get_video(filename: str):
    safe = sanitize_filename(filename)
    path = VIDEO_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    media = "video/webm" if path.suffix.lower() == ".webm" else "video/mp4"
    return FileResponse(str(path), media_type=media, filename=safe)


@app.delete("/api/end-interview/{session_id}")
async def end_interview(session_id: str):
    # For now, same as retrieving results; do not remove session state
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    # Reuse the transformation above
    resp = await interview_results(session_id)
    return resp


@app.post("/api/evaluate-response")
async def evaluate_response(payload: Dict):
    """Optional endpoint: mirror of send-message for compatibility if frontend calls this."""
    session_id = payload.get("session_id")
    answer = payload.get("answer") or payload.get("message")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    return await send_message({"session_id": session_id, "message": answer})


@app.get("/api/download-report/{session_id}")
async def download_report(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    store: SessionStore = SESSIONS[session_id]["store"]
    state = store.state
    path = generate_report(state)
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    # Serve correct media type based on extension (.pdf or .txt fallback)
    ext = p.suffix.lower()
    if ext == ".pdf":
        media = "application/pdf"
    elif ext == ".txt":
        media = "text/plain"
    else:
        media = "application/octet-stream"
    resp = FileResponse(str(p), media_type=media, filename=p.name)
    if ext != ".pdf":
        # Surface why PDF generation failed via headers for debugging
        try:
            hints = (state or {}).get("_report_hints", {}) or {}
            reason = str(hints.get("reason") or "")
            perr = str(hints.get("pdf_error") or "")
            perr_d = str(hints.get("pdf_error_detail") or "")
            if reason or perr or perr_d:
                logger.warning("report fallback to txt (reason=%s pdf_error=%s detail=%s)", reason, perr, perr_d)
                resp.headers["X-Report-Fallback-Reason"] = reason or perr
                if perr_d:
                    # keep short to avoid huge headers
                    resp.headers["X-Report-Fallback-Detail"] = perr_d[:200]
        except Exception:
            pass
    return resp


@app.get("/api/report-health")
async def report_health():
    """Check PDF generator availability in the running environment."""
    try:
            import importlib
            spec = importlib.util.find_spec("reportlab")
            present = spec is not None
            ver = None
            if present:
                import reportlab  # type: ignore
                ver = getattr(reportlab, "__version__", "unknown")
            return {"ok": True, "reportlab_present": present, "reportlab_version": ver}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/system/status")
async def system_status():
    return {"success": True, "status": "ok"}


@app.get("/")
async def root_health():
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """Accept an audio blob (WAV preferred), normalize, and transcribe.

    Improvements:
    - Always normalize to 16kHz mono WAV (even if already WAV) to reduce STT failures.
    - Cap duration to ~58s to avoid Google Web Speech hard limits.
    - Allow selecting engine and language via env vars (STT_ENGINE, STT_LANGUAGE).
      STT_ENGINE: 'google' (default) | 'google_cloud' (requires GOOGLE_CLOUD_SPEECH_CREDENTIALS)
    Fallbacks:
    - If transcoding fails (e.g., ffmpeg missing for non-WAV), return a safe placeholder.
    - If STT fails, return a placeholder acknowledging audio was received.
    """
    try:
        # Persist upload
        suffix = Path(file.filename or "audio.webm").suffix or ".webm"
        tmp_in = Path(tempfile.gettempdir()) / f"audio_{uuid.uuid4().hex}{suffix}"
        with tmp_in.open("wb") as f:
            content = await file.read()
            f.write(content)

        text: Optional[str] = None
        suffix_lower = tmp_in.suffix.lower()
        language = os.getenv("STT_LANGUAGE", "en-US")
        engine = os.getenv("STT_ENGINE", "google").lower().strip()

        t0 = time.time()
        try:
            # Lazy import for speech_recognition
            import speech_recognition as sr  # type: ignore
            logger.info(f"Transcribing audio: {tmp_in} ({tmp_in.stat().st_size} bytes) lang={language} engine={engine}")

            # Normalize to 16k mono WAV and cap to ~58s
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning, module="pydub")
                from pydub import AudioSegment  # type: ignore

            # Load with pydub; for WAV it uses stdlib, for webm it requires ffmpeg
            seg = None
            try:
                seg = AudioSegment.from_file(str(tmp_in))
            except Exception as e:
                # If this fails likely due to missing ffmpeg. Try to short-circuit when already WAV.
                if suffix_lower in (".wav", ".wave"):
                    # Last-resort: let SpeechRecognition read it directly (WAV PCM only)
                    logger.warning(f"pydub failed to load WAV; continuing with raw WAV: {e}")
                else:
                    raise

            t_load = time.time()
            tmp_wav = Path(tempfile.gettempdir()) / f"audio_norm_{uuid.uuid4().hex}.wav"
            if seg is not None:
                # resample and mono + duration cap
                seg = seg.set_frame_rate(16000).set_channels(1)
                if len(seg) > 58_000:  # milliseconds
                    seg = seg[:58_000]
                seg.export(str(tmp_wav), format="wav")
                wav_path = tmp_wav
            else:
                wav_path = tmp_in  # hope it's already a proper WAV

            recog = sr.Recognizer()
            # Slightly higher energy threshold can help in noisy inputs, but file-based ignores this mostly
            recog.energy_threshold = 200
            with sr.AudioFile(str(wav_path)) as source:
                audio_data = recog.record(source)
            t_prep = time.time()

            try:
                if engine == "google_cloud":
                    creds_json = os.getenv("GOOGLE_CLOUD_SPEECH_CREDENTIALS")
                    if not creds_json:
                        logger.error("STT_ENGINE=google_cloud set but GOOGLE_CLOUD_SPEECH_CREDENTIALS is missing")
                        raise ValueError("Missing GOOGLE_CLOUD_SPEECH_CREDENTIALS")
                    text = recog.recognize_google_cloud(audio_data, credentials_json=creds_json, language=language)
                else:
                    # default: free Google Web Speech API (rate/length limited)
                    text = recog.recognize_google(audio_data, language=language)
                if text:
                    logger.info(f"Transcription OK: {text[:80]}...")
                t_stt = time.time()
                logger.info("STT timings: load=%.2fs prep=%.2fs infer=%.2fs total=%.2fs", t_load - t0, t_prep - t_load, t_stt - t_prep, t_stt - t0)
            except sr.UnknownValueError:
                logger.warning("STT could not understand audio")
                text = None
            except sr.RequestError as e:
                logger.error(f"STT request error: {e}")
                text = None
            except Exception as e:
                logger.error(f"STT error: {e}")
                text = None
        except Exception as e:
            logger.error(f"Audio preprocessing/transcription failed: {type(e).__name__}: {e}")
            if ("ffmpeg" in str(e).lower() or "avconv" in str(e).lower()) and suffix_lower not in (".wav", ".wave"):
                logger.error("Missing ffmpeg for non-WAV uploads. Ensure frontend sends WAV (we downmix client-side).")
            text = None

        if not text:
            # Minimal placeholder so the flow continues
            size_kb = max(1, int(tmp_in.stat().st_size / 1024)) if tmp_in.exists() else 0
            text = f"[Audio received ~{size_kb} KB; transcription unavailable]"

        return {"success": True, "text": text, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint to support real-time Q&A if the frontend connects via WS
@app.websocket("/api/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    # Accept all connections; authorize by verifying session_id after accept to avoid 403 handshake errors
    await websocket.accept()
    logger.info("connection open")
    if session_id not in SESSIONS:
        # Close with policy violation if session does not exist
        logger.warning(f"WebSocket connection rejected: session {session_id} not found")
        await websocket.close(code=1008)
        logger.info("connection closed")
        return

    logger.info(f"WebSocket established for session: {session_id}")
    try:
        while True:
            msg = await websocket.receive_json()
            logger.info(f"WebSocket received: {msg.get('type')}")
            # Expect shape like: { type: 'answer' | 'ping', message?: string }
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_json({"type": "pong", "ts": int(time.time() * 1000)})
                continue;
            if mtype == "answer":
                text = msg.get("message") or ""
                # Reuse HTTP handler to process the answer and compute next question
                try:
                    result = await send_message({"session_id": session_id, "message": text})
                except Exception as e:
                    logger.error(f"Error processing answer: {e}")
                    await websocket.send_json({"type": "error", "error": str(e)})
                    continue

                # Forward next question to client in expected shape
                nq = result.get("next_question")
                payload = {"type": "question", "data": None}
                if nq and isinstance(nq, dict) and nq.get("question"):
                    payload["data"] = {"question": nq.get("question")}
                await websocket.send_json(payload)
            else:
                # Unknown message type; ignore or notify
                await websocket.send_json({"type": "warning", "message": "Unknown message type"})
    except WebSocketDisconnect:
        logger.info("connection closed")
        # Client disconnected; nothing to do
        return
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.info("connection closed")
        raise