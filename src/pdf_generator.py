"""
src/pdf_generator.py
Converts tailored resume and cover letter text into clean, ATS-friendly PDFs
using ReportLab.

Parsing strategy:
  - Section headers: ALL-CAPS lines OR lines that match common header words
    with optional markdown (## EXPERIENCE, **EXPERIENCE**, etc.)
  - Bullets: lines starting with •, -, *, –, or markdown-style hyphens
  - Job entry lines: lines containing | separating title/company/date
  - Contact block: consecutive non-empty lines right after the name
  - Everything else: body text
"""

import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Known section header keywords ────────────────────────────────────────────

SECTION_KEYWORDS = {
    "summary", "profile", "objective", "about",
    "experience", "work experience", "employment", "career history",
    "education", "academic background", "qualifications",
    "skills", "technical skills", "core competencies", "competencies",
    "certifications", "certificates", "awards", "honours", "honors",
    "projects", "publications", "languages", "interests", "volunteering",
    "references", "professional development", "training",
}


# ── Style Definitions ────────────────────────────────────────────────────────

def _build_styles():
    base = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "CandidateName",
        parent=base["Normal"],
        fontSize=20,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=4,
        leading=24,
    )
    contact_style = ParagraphStyle(
        "Contact",
        parent=base["Normal"],
        fontSize=9,
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=2,
        leading=13,
        textColor=colors.HexColor("#444444"),
    )
    section_style = ParagraphStyle(
        "Section",
        parent=base["Normal"],
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=3,
        textColor=colors.black,
        leading=13,
    )
    job_role_style = ParagraphStyle(
        "JobRole",
        parent=base["Normal"],
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceAfter=0,
        leading=14,
    )
    job_meta_style = ParagraphStyle(
        "JobMeta",
        parent=base["Normal"],
        fontSize=9,
        fontName="Helvetica-Oblique",
        spaceAfter=3,
        leading=13,
        textColor=colors.HexColor("#555555"),
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=base["Normal"],
        fontSize=10,
        fontName="Helvetica",
        leading=14,
        leftIndent=14,
        firstLineIndent=0,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontSize=10,
        fontName="Helvetica",
        leading=14,
        spaceAfter=3,
    )
    date_right_style = ParagraphStyle(
        "DateRight",
        parent=base["Normal"],
        fontSize=9,
        fontName="Helvetica",
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#666666"),
        spaceAfter=0,
        leading=13,
    )

    return {
        "name": name_style,
        "contact": contact_style,
        "section": section_style,
        "job_role": job_role_style,
        "job_meta": job_meta_style,
        "bullet": bullet_style,
        "body": body_style,
        "date_right": date_right_style,
    }


# ── Line classification helpers ───────────────────────────────────────────────

def _strip_markdown(line: str) -> str:
    """Remove markdown formatting: ##, **, __, *, _"""
    line = re.sub(r"^#{1,3}\s*", "", line)
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    line = re.sub(r"__(.*?)__", r"\1", line)
    line = re.sub(r"\*(.*?)\*", r"\1", line)
    line = re.sub(r"_(.*?)_", r"\1", line)
    return line.strip()


def _is_section_header(raw: str) -> bool:
    """
    Returns True if the line looks like a resume section header.
    Matches:
      - ALL CAPS lines (e.g. EXPERIENCE)
      - Lines matching known keywords regardless of case (e.g. Experience)
      - Markdown-headed lines (## Skills, **EDUCATION**)
    """
    stripped = raw.strip()
    if not stripped or len(stripped) > 60:
        return False

    # Strip markdown to get the real text
    clean = _strip_markdown(stripped)
    if not clean:
        return False

    # ALL CAPS (and not a bullet or contact line)
    if clean.isupper() and 2 < len(clean) < 50 and not clean.startswith("•"):
        return True

    # Matches a known keyword (whole line or whole line ≈ keyword)
    lower = clean.lower().strip(":").strip()
    if lower in SECTION_KEYWORDS:
        return True

    # Starts with ## markdown heading
    if raw.strip().startswith("#"):
        return True

    return False


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*[•\-\*–·]\s+\S", line))


def _is_job_entry(line: str) -> bool:
    """
    Detect lines like: "Software Engineer | Acme Corp | 2022 – Present"
    or "Software Engineer  Acme Corp  2022-2024"
    Must have at least one separator and contain some alphabetic content.
    """
    stripped = line.strip()
    has_separator = bool(re.search(r"\s*[|–—]\s*", stripped))
    has_alpha = bool(re.search(r"[A-Za-z]{3,}", stripped))
    # Reasonable length for a job line
    return has_separator and has_alpha and 10 < len(stripped) < 120


def _is_date_only(line: str) -> bool:
    """Lines that are purely date ranges like '2020 – Present' or 'Jan 2019 – Mar 2022'"""
    stripped = line.strip()
    return bool(re.match(
        r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})"
        r".{0,30}(Present|Current|\d{4})$",
        stripped, re.IGNORECASE
    ))


def _split_job_entry(line: str):
    """
    Split a job entry line into (role, meta) parts.
    e.g. 'Software Engineer | Acme Corp | 2022 – Present'
    → role = 'Software Engineer', meta = 'Acme Corp | 2022 – Present'
    """
    parts = re.split(r"\s*[|–—]\s*", line.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return line.strip(), ""


# ── Resume parser ─────────────────────────────────────────────────────────────

def _parse_resume_to_flowables(text: str, styles: dict) -> list:
    story = []
    lines = text.split("\n")

    # Remove leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return story

    i = 0

    # ── Name (first non-empty line) ───────────────────────────────────────────
    name_line = _strip_markdown(lines[0])
    story.append(Paragraph(name_line, styles["name"]))
    i = 1

    # ── Contact block (consecutive non-empty lines until blank or section) ────
    contact_parts = []
    while i < len(lines):
        l = lines[i].strip()
        if not l:
            i += 1
            break
        if _is_section_header(lines[i]):
            break
        contact_parts.append(_strip_markdown(l))
        i += 1

    if contact_parts:
        # Join on one line with separators if short, else stack them
        joined = "  |  ".join(contact_parts)
        if len(joined) <= 100:
            story.append(Paragraph(joined, styles["contact"]))
        else:
            for cp in contact_parts:
                story.append(Paragraph(cp, styles["contact"]))

    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=4))

    # ── Body ──────────────────────────────────────────────────────────────────
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Blank line → small spacer
        if not stripped:
            story.append(Spacer(1, 3))
            i += 1
            continue

        # Section header
        if _is_section_header(raw):
            clean_header = _strip_markdown(stripped).upper()
            # Group header + following content to avoid orphaned headers
            story.append(Spacer(1, 8))
            story.append(Paragraph(clean_header, styles["section"]))
            story.append(HRFlowable(
                width="100%", thickness=0.4,
                color=colors.HexColor("#aaaaaa"), spaceAfter=4
            ))
            i += 1
            continue

        # Bullet point
        if _is_bullet(raw):
            clean = re.sub(r"^\s*[•\-\*–·]\s*", "", stripped)
            clean = _strip_markdown(clean)
            story.append(Paragraph(f"• {clean}", styles["bullet"]))
            i += 1
            continue

        # Date-only line (standalone dates under a job)
        if _is_date_only(stripped):
            story.append(Paragraph(stripped, styles["job_meta"]))
            i += 1
            continue

        # Job entry line (Role | Company | Date)
        if _is_job_entry(raw):
            role, meta = _split_job_entry(stripped)
            story.append(Paragraph(_strip_markdown(role), styles["job_role"]))
            if meta:
                story.append(Paragraph(_strip_markdown(meta), styles["job_meta"]))
            i += 1
            continue

        # Bold-only line (e.g. **Company Name**) → treat as sub-heading
        if re.match(r"^\*\*.+\*\*$", stripped) or re.match(r"^__.+__$", stripped):
            clean = _strip_markdown(stripped)
            story.append(Paragraph(clean, styles["job_role"]))
            i += 1
            continue

        # Default: body text
        clean = _strip_markdown(stripped)
        if clean:
            story.append(Paragraph(clean, styles["body"]))
        i += 1

    return story


# ── Cover letter parser ───────────────────────────────────────────────────────

def _parse_letter_to_flowables(text: str, styles: dict) -> list:
    story = []

    # Split on double newlines to get paragraphs
    raw_paras = re.split(r"\n{2,}", text.strip())

    for para in raw_paras:
        para = para.strip()
        if not para:
            continue

        # Collapse internal single newlines to spaces
        para = re.sub(r"\n", " ", para)
        clean = _strip_markdown(para)

        if clean:
            story.append(Paragraph(clean, styles["body"]))
            story.append(Spacer(1, 10))

    return story


# ── Public API ────────────────────────────────────────────────────────────────

def generate_resume_pdf(text: str, output_path: str) -> str:
    """Render resume text to a PDF file. Returns the output path."""
    styles = _build_styles()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Tailored Resume",
    )

    story = _parse_resume_to_flowables(text, styles)
    doc.build(story)
    return output_path


def generate_cover_letter_pdf(text: str, output_path: str) -> str:
    """Render cover letter text to a PDF file. Returns the output path."""
    styles = _build_styles()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title="Cover Letter",
    )

    story = _parse_letter_to_flowables(text, styles)
    doc.build(story)
    return output_path
