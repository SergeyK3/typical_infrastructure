"""ReportLab PDF assembly for psychological testing exports."""

from __future__ import annotations

import io
import os
from copy import deepcopy
from typing import Any, Callable, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DEFAULT_MARGIN = 18 * mm


def _register_cyrillic_fonts() -> tuple[str, str, str]:
    """Return (body_font, title_font, bold_font) with Cyrillic support when possible."""
    windows_fonts = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
    candidates = [
        ("arial.ttf", "PT-Arial"),
        ("arialbd.ttf", "PT-Arial-Bold"),
        ("times.ttf", "PT-Times"),
        ("timesbd.ttf", "PT-Times-Bold"),
    ]
    registered: set[str] = set()
    for filename, name in candidates:
        path = os.path.join(windows_fonts, filename)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered.add(name)
            except Exception:
                pass
    body = "PT-Arial" if "PT-Arial" in registered else (
        "PT-Times" if "PT-Times" in registered else "Helvetica"
    )
    title = "PT-Arial-Bold" if "PT-Arial-Bold" in registered else (
        "PT-Times-Bold" if "PT-Times-Bold" in registered else "Helvetica-Bold"
    )
    bold = title
    return body, title, bold


class PdfComposer:
    """Build PDF story elements with Cyrillic-friendly fonts."""

    def __init__(self) -> None:
        self.body_font, self.title_font, self.bold_font = _register_cyrillic_fonts()
        self.styles = self._build_styles()
        self._page_width = A4[0] - 2 * DEFAULT_MARGIN

    def _build_styles(self):
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="PTMainTitle",
                parent=styles["Title"],
                fontName=self.title_font,
                fontSize=16,
                textColor=colors.HexColor("#2C3E50"),
                spaceAfter=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTSectionTitle",
                parent=styles["Heading1"],
                fontName=self.title_font,
                fontSize=13,
                textColor=colors.HexColor("#2C3E50"),
                spaceBefore=10,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTSubTitle",
                parent=styles["Heading2"],
                fontName=self.bold_font,
                fontSize=11,
                textColor=colors.HexColor("#34495E"),
                spaceBefore=6,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTBody",
                parent=styles["Normal"],
                fontName=self.body_font,
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#2C2C2C"),
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTMeta",
                parent=styles["Normal"],
                fontName=self.body_font,
                fontSize=9,
                textColor=colors.HexColor("#555555"),
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTBullet",
                parent=styles["Normal"],
                fontName=self.body_font,
                fontSize=10,
                leading=13,
                leftIndent=12,
                bulletIndent=0,
                textColor=colors.HexColor("#2C2C2C"),
                spaceAfter=3,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PTQACell",
                parent=styles["Normal"],
                fontName=self.body_font,
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#2C2C2C"),
            )
        )
        return styles

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

    def paragraph(self, text: str, style: str = "PTBody") -> Paragraph:
        return Paragraph(self._escape(text), self.styles[style])

    def section_title(self, text: str) -> Paragraph:
        return Paragraph(self._escape(text), self.styles["PTSectionTitle"])

    def subheading(self, text: str) -> Paragraph:
        return Paragraph(self._escape(text), self.styles["PTSubTitle"])

    def main_title(self, text: str) -> Paragraph:
        return Paragraph(self._escape(text), self.styles["PTMainTitle"])

    def bullets(self, items: list[str]) -> list[Paragraph]:
        return [
            Paragraph(self._escape(f"• {item}"), self.styles["PTBullet"])
            for item in items
            if item.strip()
        ]

    def chart_image(self, png_bytes: bytes, *, width_mm: float = 160, height_mm: float = 90) -> Image:
        return Image(
            io.BytesIO(png_bytes),
            width=width_mm * mm,
            height=height_mm * mm,
        )

    def qa_table(self, rows: list[tuple[str, str, str]]) -> list[Any]:
        """Render Q/A rows as a simple table (№, вопрос, ответ)."""
        if not rows:
            return []
        data = [
            [
                Paragraph("<b>№</b>", self.styles["PTQACell"]),
                Paragraph("<b>Вопрос</b>", self.styles["PTQACell"]),
                Paragraph("<b>Ответ</b>", self.styles["PTQACell"]),
            ]
        ]
        col_widths = [12 * mm, self._page_width * 0.58, self._page_width * 0.28]
        for num, question, answer in rows:
            data.append(
                [
                    Paragraph(self._escape(num), self.styles["PTQACell"]),
                    Paragraph(self._escape(question), self.styles["PTQACell"]),
                    Paragraph(self._escape(answer), self.styles["PTQACell"]),
                ]
            )
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BDC3C7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return [table, Spacer(1, 4)]

    def build_pdf_bytes(
        self,
        story: Iterable[Any],
        *,
        page_numbers: bool = False,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=DEFAULT_MARGIN,
            rightMargin=DEFAULT_MARGIN,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            title="Psychological Testing Report",
        )
        story_list = list(story)
        total_pages = 0
        if page_numbers:
            total_pages = self._count_pages(story_list, doc)

        def _on_page(canvas, _doc):
            if page_numbers and total_pages > 0:
                canvas.saveState()
                canvas.setFont(self.body_font, 9)
                page_num = canvas.getPageNumber()
                text = f"Стр. {page_num} из {total_pages}"
                canvas.drawRightString(A4[0] - DEFAULT_MARGIN, A4[1] - 12 * mm, text)
                canvas.restoreState()

        doc.build(story_list, onFirstPage=_on_page, onLaterPages=_on_page)
        buffer.seek(0)
        return buffer.read()

    def _count_pages(self, story: list[Any], template: SimpleDocTemplate) -> int:
        temp = io.BytesIO()
        counter_doc = SimpleDocTemplate(
            temp,
            pagesize=template.pagesize,
            leftMargin=template.leftMargin,
            rightMargin=template.rightMargin,
            topMargin=template.topMargin,
            bottomMargin=template.bottomMargin,
        )
        counter_doc.build(deepcopy(story))
        return counter_doc.page
