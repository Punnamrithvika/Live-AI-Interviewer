import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_utils import DATA_DIR, timestamp, sanitize_filename


class SessionStore:
    """Simple JSON-backed storage for interview sessions."""

    def __init__(self, candidate_name: str, role: str):
        safe_name = sanitize_filename(candidate_name)
        safe_role = sanitize_filename(role)
        self.session_id = f"{safe_name}_{safe_role}_{timestamp()}"
        self.path = DATA_DIR / f"{self.session_id}.json"
        self.state: Dict[str, Any] = {
            "candidate": {"name": candidate_name, "role": role},
            "phases": {"introduction": [], "projects": [], "skills": []},
            "projects": [],
            "skills_summary": {},
        }
        self._persist()

    def _persist(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def add_project_summaries(self, projects: List[Dict[str, str]]):
        self.state["projects"] = projects
        self._persist()

    def add_qa(self, phase: str, question: str, answer: str, score: float, feedback: str | None = None):
        entry = {"question": question, "answer": answer, "score": score}
        if feedback:
            entry["feedback"] = feedback
        self.state["phases"].setdefault(phase, [])
        self.state["phases"][phase].append(entry)
        self._persist()

    def add_skill_result(self, skill: str, level: str, passed: bool, details: Dict[str, Any]):
        skills = self.state["skills_summary"].setdefault(skill, {})
        skills[level] = {"passed": passed, **details}
        self._persist()

    def get_last_responses(self, phase: str, n: int = 2) -> List[str]:
        items = self.state.get("phases", {}).get(phase, [])
        if isinstance(items, list):
            return [it.get("answer", "") for it in items[-n:]]
        # If mis-typed, return empty
        return []

    def export_path(self) -> Path:
        return self.path
