"""Render RD_Report.md to the submission PDF with ReportLab.

Run with the project interpreter after installing ReportLab:
    python scripts/render_rd_report.py
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RD_Report.md"
OUTPUT = ROOT / "AI-4016_GigBid_RD_Report.pdf"
NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#1F4E79")
PALE_BLUE = colors.HexColor("#EAF0F7")
GRAY = colors.HexColor("#5B6573")


def _plain_ascii(text: str) -> str:
    return (
        text.replace("κ", "kappa")
        .replace("≥", ">=")
        .replace("≤", "<=")
        .replace("→", "->")
        .replace("–", "-")
        .replace("—", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
        .replace("…", "...")
        .replace("·", "|")
    )


def _inline_markup(text: str) -> str:
    escaped = html.escape(_plain_ascii(text), quote=False)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", escaped)
    return escaped


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=NAVY,
            spaceBefore=5,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "SubHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=BLUE,
            spaceBefore=5,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "MinorHeading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11,
            textColor=BLUE,
            spaceBefore=4,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#202833"),
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "meta": ParagraphStyle(
            "Metadata",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=GRAY,
            spaceAfter=4,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.1,
            leading=8.4,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.1,
            leading=8.4,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "bullet": ParagraphStyle(
            "BulletBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=3,
        ),
    }


def _table_flowable(rows: list[list[str]], width: float, styles: dict[str, ParagraphStyle]) -> Table:
    columns = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (columns - len(row)) for row in rows]
    data = [
        [
            Paragraph(_inline_markup(cell), styles["table_header" if row_index == 0 else "table"])
            for cell in row
        ]
        for row_index, row in enumerate(normalized_rows)
    ]
    weights = []
    for column in range(columns):
        longest = max(len(row[column]) for row in normalized_rows)
        weights.append(min(5.5, max(1.0, longest**0.48)))
    total_weight = sum(weights)
    col_widths = [width * weight / total_weight for weight in weights]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C4D3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _is_table_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line)) and "-" in line


def _build_story(markdown: str, width: float) -> list[object]:
    styles = _styles()
    story: list[object] = []
    paragraph: list[str] = []
    lines = markdown.splitlines()

    def flush_paragraph() -> None:
        if paragraph:
            text = " ".join(part.strip() for part in paragraph)
            story.append(Paragraph(_inline_markup(text), styles["body"]))
            paragraph.clear()

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            flush_paragraph()
            index += 1
            continue
        if line == "[[PAGEBREAK]]":
            flush_paragraph()
            story.append(PageBreak())
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                candidate = lines[index].strip()
                if not _is_table_separator(candidate):
                    table_lines.append(candidate)
                index += 1
            table_rows = [
                [cell.strip() for cell in row.strip("|").split("|")]
                for row in table_lines
            ]
            if table_rows:
                story.append(_table_flowable(table_rows, width, styles))
                story.append(Spacer(1, 6))
            continue
        if line.startswith("#"):
            flush_paragraph()
            level = len(line) - len(line.lstrip("#"))
            heading = line[level:].strip()
            style = styles["title"] if level == 1 and heading != "Appendices" else styles[
                {1: "h2", 2: "h2", 3: "h3"}.get(level, "h4")
            ]
            story.append(Paragraph(_inline_markup(heading), style))
            index += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            story.append(Paragraph(f"- {_inline_markup(line[2:])}", styles["bullet"]))
            index += 1
            continue
        paragraph.append(line)
        index += 1
    flush_paragraph()
    return story


def _decorate(canvas, document) -> None:
    canvas.saveState()
    page_width, page_height = letter
    canvas.setStrokeColor(colors.HexColor("#C7D0DB"))
    canvas.setLineWidth(0.5)
    canvas.line(document.leftMargin, page_height - 34, page_width - document.rightMargin, page_height - 34)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(document.leftMargin, page_height - 26, "AI-4016 | R&D ASSIGNMENT | GIGBID")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(page_width / 2, 22, f"GigBid | AI-4016 | Page {document.page}")
    canvas.restoreState()


def render(source: Path = SOURCE, output: Path = OUTPUT) -> None:
    document = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=42,
        leftMargin=42,
        topMargin=48,
        bottomMargin=38,
        title="AI-4016 GigBid R&D Engineering Design Review",
        author="AI-4016",
    )
    story = _build_story(source.read_text(encoding="utf-8"), document.width)
    document.build(story, onFirstPage=_decorate, onLaterPages=_decorate)


if __name__ == "__main__":
    render()
