from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict

from fpdf import FPDF

from .file_utils import REPORTS_DIR, sanitize_filename


def _safe_text(s: str, max_token: int = 60) -> str:
    """Insert spaces into very long tokens to avoid FPDF width errors."""
    parts = []
    for tok in s.split():
        if len(tok) > max_token:
            chunks = [tok[i:i+max_token] for i in range(0, len(tok), max_token)]
            parts.append(" ".join(chunks))
        else:
            parts.append(tok)
    return " ".join(parts)


class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Interview Report', border=0, ln=1, align='C')
        self.ln(2)


def _write_text_report(state: Dict) -> str:
    candidate = state.get('candidate', {})
    candidate_name = candidate.get('name', 'Candidate')
    role = candidate.get('role', 'Role')
    safe_name = sanitize_filename(candidate_name)
    filename = f"{safe_name}_{datetime.now().strftime('%Y-%m-%d')}.txt"
    out_path = Path(REPORTS_DIR) / filename

    lines = []
    lines.append(f"Candidate: {candidate_name}")
    lines.append(f"Role: {role}")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    projects = state.get('projects', [])
    if projects:
        lines.append('Projects:')
        for p in projects:
            title = p.get('project_title', '-')
            summary = p.get('summary', '')
            lines.append(f"- {title}: {summary}")
        lines.append("")

    phases = state.get('phases', {})
    for phase_name in ('introduction', 'projects', 'skills'):
        items = phases.get(phase_name, []) if isinstance(phases.get(phase_name), list) else []
        if items:
            lines.append(phase_name.capitalize())
            for idx, item in enumerate(items, start=1):
                q = item.get('question', '')
                a = item.get('answer', '')
                s = item.get('score', 0)
                lines.append(f"Question {idx}: {q}")
                lines.append(f"Response {idx}: {a}")
                lines.append(f"Score: {s}")
                fb = item.get('feedback')
                if fb:
                    lines.append(f"Feedback: {fb}")
            lines.append("")

    skills_summary = state.get('skills_summary', {})
    if skills_summary:
        lines.append('Skills Summary:')
        for skill, levels in skills_summary.items():
            lines.append(skill)
            for level, detail in levels.items():
                passed = detail.get('passed', False)
                passes = detail.get('passes', 0)
                fails = detail.get('fails', 0)
                asked = detail.get('asked')
                suffix = f", asked={asked}" if asked is not None else ""
                lines.append(f"  - {level}: {'Passed' if passed else 'Not proficient'} (passes={passes}, fails={fails}{suffix})")
                fb = detail.get('feedback')
                if fb:
                    lines.append(f"    Feedback: {fb}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding='utf-8')
    return str(out_path)


def generate_report(state: Dict) -> str:
    candidate = state.get('candidate', {})
    candidate_name = candidate.get('name', 'Candidate')
    role = candidate.get('role', 'Role')

    try:
        pdf = PDFReport()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"Candidate: {candidate_name}", ln=1)
        pdf.cell(0, 10, f"Role: {role}", ln=1)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1)

        # Projects summary
        projects = state.get('projects', [])
        if projects:
            pdf.ln(4)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Projects:', ln=1)
            pdf.set_font('Arial', '', 11)
            for p in projects:
                title = p.get('project_title', '-')
                summary = _safe_text(p.get('summary', ''))
                pdf.multi_cell(0, 8, _safe_text(f"- {title}: {summary}"))

        # Q&A sections
        phases = state.get('phases', {})
        for phase_name in ('introduction', 'projects', 'skills'):
            items = phases.get(phase_name, []) if isinstance(phases.get(phase_name), list) else []
            if items:
                pdf.ln(4)
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, phase_name.capitalize(), ln=1)
                pdf.set_font('Arial', '', 11)
                for idx, item in enumerate(items, start=1):
                    q = _safe_text(item.get('question', ''))
                    a = _safe_text(item.get('answer', ''))
                    s = item.get('score', 0)
                    pdf.set_font('Arial', 'B', 11)
                    pdf.multi_cell(0, 8, f"Question {idx}:")
                    pdf.set_font('Arial', '', 11)
                    pdf.multi_cell(0, 8, q)
                    pdf.set_font('Arial', 'B', 11)
                    pdf.multi_cell(0, 8, f"Response {idx}:")
                    pdf.set_font('Arial', '', 11)
                    pdf.multi_cell(0, 8, a)
                    pdf.cell(0, 8, f"Score: {s}", ln=1)
                    fb = item.get('feedback')
                    if fb:
                        pdf.multi_cell(0, 8, _safe_text(f"Feedback: {fb}"))

        # Skills summary
        skills_summary = state.get('skills_summary', {})
        if skills_summary:
            pdf.ln(4)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Skills Summary:', ln=1)
            pdf.set_font('Arial', '', 11)
            for skill, levels in skills_summary.items():
                pdf.cell(0, 8, f"{skill}", ln=1)
                for level, detail in levels.items():
                    passed = detail.get('passed', False)
                    passes = detail.get('passes', 0)
                    fails = detail.get('fails', 0)
                    pdf.cell(0, 8, f"  - {level}: {'Passed' if passed else 'Not proficient'} (passes={passes}, fails={fails})", ln=1)
                    fb = detail.get('feedback')
                    if fb:
                        pdf.multi_cell(0, 8, _safe_text(f"    Feedback: {fb}"))

        safe_name = sanitize_filename(candidate_name)
        filename = f"{safe_name}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        out_path = Path(REPORTS_DIR) / filename
        pdf.output(str(out_path))
        return str(out_path)
    except Exception:
        # If PDF generation fails for any reason, write a .txt report instead
        return _write_text_report(state)
