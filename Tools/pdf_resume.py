"""
pdf_resume.py (Generic Version)
-------------------------------
Generates a professional PDF resume using a structured profile dictionary.
This allows Bunny.AI to create resumes for ANY scraped portfolio.
"""

import os
import tempfile

def generate_resume_pdf(profile_data: dict, output_filename: str = None) -> str:
    """
    Generate a professional PDF resume from a profile dictionary.
    
    profile_data structure:
    {
        "name": "...",
        "title": "...",
        "contact": {"email": "...", "phone": "...", "location": "...", "website": "..."},
        "summary": "...",
        "skills": {"Category": "skill1, skill2...", ...},
        "experience": [{"role": "...", "company": "...", "period": "...", "points": ["..."]}],
        "education": [{"degree": "...", "school": "...", "period": "...", "detail": "..."}],
        "projects": [["Name", "Description"], ...],
        "achievements": ["..."],
        "certifications": ["..."]
    }
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether
        )
    except ImportError:
        return "Error: reportlab is not installed."

    name_slug = profile_data.get("name", "Resume").replace(" ", "_")
    if not output_filename:
        output_filename = f"{name_slug}_Resume.pdf"
    
    output_path = os.path.join(tempfile.gettempdir(), output_filename)

    # Styles (Strictly unique names)
    base = getSampleStyleSheet()
    DARK_BLUE = colors.HexColor("#1a237e")
    ACCENT = colors.HexColor("#3949ab")
    TEXT = colors.HexColor("#212121")

    styles = {
        "name": ParagraphStyle("Z_Name", fontName="Helvetica-Bold", fontSize=22, textColor=colors.white, alignment=TA_CENTER),
        "title": ParagraphStyle("Z_Title", fontName="Helvetica", fontSize=12, textColor=colors.HexColor("#c5cae9"), alignment=TA_CENTER),
        "section": ParagraphStyle("Z_Sect", fontName="Helvetica-Bold", fontSize=11, textColor=DARK_BLUE, spaceBefore=10, spaceAfter=2),
        "body": ParagraphStyle("Z_Body", fontName="Helvetica", fontSize=9, textColor=TEXT, leading=12, alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("Z_Bullet", fontName="Helvetica", fontSize=9, textColor=TEXT, leading=12, leftIndent=12),
        "job": ParagraphStyle("Z_Job", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT),
        "sub": ParagraphStyle("Z_Sub", fontName="Helvetica-Oblique", fontSize=8, textColor=colors.grey),
    }

    story = []

    # Header
    c = profile_data.get("contact", {})
    contact_line = f"{c.get('email', '')}  |  {c.get('phone', '')}  |  {c.get('location', '')}  |  {c.get('website', '')}"
    
    header_data = [
        [Paragraph(profile_data.get("name", "Unknown"), styles["name"])],
        [Paragraph(profile_data.get("title", ""), styles["title"])],
        [Paragraph(contact_line, ParagraphStyle("Z_C", fontName="Helvetica", fontSize=8, textColor=colors.white, alignment=TA_CENTER))]
    ]
    header = Table(header_data, colWidths=[A4[0] - 3*cm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BLUE),
        ("ROUNDEDCORNERS", [6]),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.5*cm))

    # Summary
    story.append(Paragraph("PROFESSIONAL SUMMARY", styles["section"]))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    story.append(Paragraph(profile_data.get("summary", ""), styles["body"]))

    # Skills Table
    story.append(Paragraph("TECHNICAL SKILLS", styles["section"]))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    skill_data = [[Paragraph(k, styles["job"]), Paragraph(v, styles["body"])] for k, v in profile_data.get("skills", {}).items()]
    if skill_data:
        t = Table(skill_data, colWidths=[4*cm, 13*cm])
        t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
        story.append(t)

    # Experience
    story.append(Paragraph("EXPERIENCE", styles["section"]))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    for exp in profile_data.get("experience", []):
        story.append(KeepTogether([
            Paragraph(f"{exp.get('role')} — {exp.get('company')}", styles["job"]),
            Paragraph(exp.get("period", ""), styles["sub"]),
            *[Paragraph(f"• {p}", styles["bullet"]) for p in exp.get("points", [])],
            Spacer(1, 0.2*cm)
        ]))

    # Education
    story.append(Paragraph("EDUCATION", styles["section"]))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    for edu in profile_data.get("education", []):
        story.append(Paragraph(f"{edu.get('degree')} — {edu.get('school')}", styles["job"]))
        story.append(Paragraph(f"{edu.get('period')}  |  {edu.get('detail')}", styles["sub"]))

    # Projects
    if profile_data.get("projects"):
        story.append(Paragraph("KEY PROJECTS", styles["section"]))
        story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
        for name, desc in profile_data.get("projects", []):
            story.append(Paragraph(f"<b>{name}</b>: {desc}", styles["body"]))

    doc = SimpleDocTemplate(output_path, pagesize=A4, margin=(1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm))
    doc.build(story)

    return f"FILE_PATH:{output_path}"
