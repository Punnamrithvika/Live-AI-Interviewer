from __future__ import annotations

from typing import Dict, List

from ..utils.storage import SessionStore
from ..extraction.resume_extractor import extract_and_store_projects
from ..questions.introduction_phase import run_intro_interaction
from ..questions.projects_phase import run_projects_interaction
from ..questions.skills_phase import run_skills_interaction


class InterviewController:
    def __init__(self, candidate_info: Dict[str, str]):
        self.candidate_info = candidate_info
        self.store = SessionStore(candidate_info.get("name", "Candidate"), candidate_info.get("role", "Role"))

    def start_interview(self, resume_path: str, skills: List[str], play_audio: bool = True) -> None:
        # Extract projects
        extract_and_store_projects(resume_path, self.store)
        # Intro phase
        self.run_introduction_phase(play_audio=play_audio)
        # Projects phase
        self.run_project_phase(play_audio=play_audio)
        # Skills phase
        self.run_skills_phase(skills=skills, play_audio=play_audio)

    def run_introduction_phase(self, play_audio: bool = True) -> None:
        run_intro_interaction(self.store, play_audio=play_audio)

    def run_project_phase(self, play_audio: bool = True) -> None:
        run_projects_interaction(self.store, play_audio=play_audio)

    def run_skills_phase(self, skills: List[str], play_audio: bool = True) -> None:
        run_skills_interaction(self.store, skills=skills, play_audio=play_audio)

    def compile_results(self) -> Dict:
        return self.store.state
