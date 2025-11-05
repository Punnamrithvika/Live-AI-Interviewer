from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

# NOTE: Avoid importing heavy/optional libs at module import time to prevent server startup failures.
# We'll import fitz (PyMuPDF) and python-docx inside helper functions only when needed.

from ..utils.cohere_client import generate_text
from ..utils.storage import SessionStore


def _extract_text_pdf(path: Path) -> str:
    try:
        import fitz  # type: ignore  # PyMuPDF
    except Exception as e:
        raise RuntimeError("PDF extraction requires PyMuPDF (fitz) to be installed.") from e

    text_parts: List[str] = []
    with fitz.open(path) as doc:  # type: ignore[attr-defined]
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _extract_text_docx(path: Path) -> str:
    
    from docx import Document as DocxDocument  # type: ignore
    
    doc = DocxDocument(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_resume_text(resume_path: str) -> str:
    p = Path(resume_path)
    if not p.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_pdf(p)
    elif suffix in (".docx", ".doc"):
        return _extract_text_docx(p)
    else:
        raise ValueError("Unsupported resume format. Use .pdf or .docx")


def summarize_projects_from_resume_text(resume_text: str) -> List[Dict[str, str]]:
    prompt = (
        "Extract all major projects from the following resume text.\n"
        "Summarize each project in 2-3 lines.\n"
        "Return output as JSON array with objects of shape: \n"
        "[{\"project_title\": \"...\", \"summary\": \"...\"}]\n\n"
        f"Resume text:\n{resume_text[:8000]}\n"  # limit to avoid overlong prompts
    )

    raw = generate_text(prompt, json_mode=True)
    # Try to locate JSON within the response
    json_str = raw
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        json_str = raw[start : end + 1]
    try:
        data = json.loads(json_str)
        # Ensure schema
        projects = []
        for item in data:
            title = str(item.get("project_title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if title or summary:
                projects.append({"project_title": title, "summary": summary})
        return projects
    except Exception:
        # Fallback: return a single generic item if parsing fails
        return [{"project_title": "Project", "summary": "Summary not available."}]


def extract_and_store_projects(resume_path: str, store: SessionStore) -> List[Dict[str, str]]:
    text = extract_resume_text(resume_path)
    projects = summarize_projects_from_resume_text(text)
    store.add_project_summaries(projects)
    return projects
