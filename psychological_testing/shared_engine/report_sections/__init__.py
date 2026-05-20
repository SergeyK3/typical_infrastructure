"""Plug-in PDF section renderers (Phase D)."""

from psychological_testing.shared_engine.report_sections.appendix_qa import (
    render_appendix_qa,
)
from psychological_testing.shared_engine.report_sections.mbti_section import (
    render_mbti_section,
)
from psychological_testing.shared_engine.report_sections.test_section import (
    render_test_section,
)

__all__ = [
    "render_appendix_qa",
    "render_mbti_section",
    "render_test_section",
]
