from __future__ import annotations

import argparse
import json
from typing import List

from src.orchestrator.interview_controller import InterviewController
from src.utils.report_generator import generate_report


def parse_args():
    p = argparse.ArgumentParser(description="AI Interview System - Backend Orchestrator")
    p.add_argument("--name", required=True, help="Candidate name")
    p.add_argument("--role", required=True, help="Role name")
    p.add_argument("--skills", required=True, help="Comma-separated skills (e.g., python,react,system design)")
    p.add_argument("--resume", required=True, help="Path to resume .pdf or .docx")
    p.add_argument("--no-audio", action="store_true", help="Disable audio playback (useful for CI/testing)")
    return p.parse_args()


def main():
    args = parse_args()
    skills: List[str] = [s.strip() for s in args.skills.split(",") if s.strip()]

    controller = InterviewController({"name": args.name, "role": args.role})
    controller.start_interview(resume_path=args.resume, skills=skills, play_audio=not args.no_audio)
    state = controller.compile_results()

    report_path = generate_report(state)
    print(json.dumps({"report": report_path, "session_data": controller.store.export_path().as_posix()}, indent=2))


if __name__ == "__main__":
    main()
