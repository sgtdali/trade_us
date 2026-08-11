"""Renders the Markdown fundamental-analysis report from a report context
built by :func:`fundamental_pipeline.reports.context.build_report_context`.
"""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..paths import repo_path

_TEMPLATE_BY_SECTOR = {
    "aviation": "aviation.tr.md.j2",
    "generic": "standard-corporate.tr.md.j2",
}


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(repo_path("templates", "reports"))),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_report(report_context: dict) -> str:
    """Render the full Markdown report. Pure function over the given
    context; does not read any file itself (the caller is responsible for
    building the context from an AnalysisContext + generated data)."""
    template_name = _TEMPLATE_BY_SECTOR.get(report_context["sector_module"], "standard-corporate.tr.md.j2")
    env = _environment()
    template = env.get_template(template_name)
    rendered = template.render(**report_context)
    # Collapse the runs of blank lines that Jinja control blocks leave behind
    # so output is stable and readable, and ensure a single trailing newline.
    lines = [line.rstrip() for line in rendered.splitlines()]
    collapsed: list[str] = []
    for line in lines:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return "\n".join(collapsed) + "\n"
