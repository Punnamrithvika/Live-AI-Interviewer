from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

# ReportLab is the sole PDF engine now
try:  # pragma: no cover
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover
    REPORTLAB_AVAILABLE = False

from .file_utils import REPORTS_DIR, sanitize_filename


def _normalize_text(s: str) -> str:
    if s is None:
        return ""
    return str(s)


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

    # Include debug hints when PDF generation failed
    hints = (state or {}).get('_report_hints')
    if hints:
        lines.append('')
        lines.append('Report Hints (debug):')
        try:
            for k, v in hints.items():
                lines.append(f"- {k}: {v}")
        except Exception:
            # best-effort serialization
            lines.append(str(hints))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding='utf-8')
    return str(out_path)


def _generate_pdf_reportlab(state: Dict) -> str:
    """Generate report using ReportLab (robust wrapping and layout)."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab_not_installed")

    candidate = state.get('candidate', {})
    candidate_name = candidate.get('name', 'Candidate')
    role = candidate.get('role', 'Role')

    safe_name = sanitize_filename(candidate_name)
    filename = f"{safe_name}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    out_path = Path(REPORTS_DIR) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    story: List = []

    story.append(Paragraph("Interview Report", styles['Title']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Candidate: {candidate_name}", styles['Normal']))
    story.append(Paragraph(f"Role: {role}", styles['Normal']))
    story.append(Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M'), styles['Normal']))
    story.append(Spacer(1, 10))

    projects = state.get('projects', [])
    if projects:
        story.append(Paragraph('Projects', styles['Heading2']))
        for p in projects:
            title = p.get('project_title', '-')
            summary = p.get('summary', '')
            story.append(Paragraph(f"- <b>{title}</b>: {summary}", styles['Normal']))
        story.append(Spacer(1, 8))

    phases = state.get('phases', {})
    for phase_name in ('introduction', 'projects', 'skills'):
        items = phases.get(phase_name, []) if isinstance(phases.get(phase_name), list) else []
        if items:
            story.append(Paragraph(phase_name.capitalize(), styles['Heading2']))
            for idx, item in enumerate(items, start=1):
                q = item.get('question', '')
                a = item.get('answer', '')
                s = item.get('score', 0)
                story.append(Paragraph(f"<b>Question {idx}:</b>", styles['Normal']))
                story.append(Paragraph(q, styles['Normal']))
                story.append(Paragraph(f"<b>Response {idx}:</b>", styles['Normal']))
                story.append(Paragraph(a, styles['Normal']))
                story.append(Paragraph(f"Score: {s}", styles['Normal']))
                fb = item.get('feedback')
                if fb:
                    story.append(Paragraph(f"Feedback: {fb}", styles['Italic']))
            story.append(Spacer(1, 6))

    skills_summary = state.get('skills_summary', {})
    if skills_summary:
        story.append(Paragraph('Skills Summary', styles['Heading2']))
        for skill, levels in skills_summary.items():
            story.append(Paragraph(f"{skill}", styles['Heading3']))
            for level, detail in levels.items():
                passed = detail.get('passed', False)
                passes = detail.get('passes', 0)
                fails = detail.get('fails', 0)
                story.append(Paragraph(
                    f"&nbsp;&nbsp;- {level}: {'Passed' if passed else 'Not proficient'} (passes={passes}, fails={fails})",
                    styles['Normal']
                ))
                fb = detail.get('feedback')
                if fb:
                    story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Feedback: {fb}", styles['Italic']))

    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER, title="Interview Report")
    doc.build(story)
    return str(out_path)


def generate_report(state: Dict) -> str:
    candidate = state.get('candidate', {})
    candidate_name = candidate.get('name', 'Candidate')
    role = candidate.get('role', 'Role')
    if REPORTLAB_AVAILABLE:
        try:
            return _generate_pdf_reportlab(state)
        except Exception as e:
            try:
                hints = state.get('_report_hints', {}) or {}
                hints['reportlab_error'] = str(e)
                state['_report_hints'] = hints
            except Exception:
                pass
    # If ReportLab missing, fallback to text
    return _write_text_report(state)
